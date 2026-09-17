#define _GNU_SOURCE

#include "ipc.h"

#include <errno.h>
#include <stdio.h>
#include <limits.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <sys/ipc.h>
#include <sys/sem.h>
#include <sys/shm.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#include "record.h"
#include "timing.h"
#include "runtime.h"

enum {
    SEMAPHORE_EMPTY = 0,
    SEMAPHORE_FULL = 1,
    SEMAPHORE_PRODUCER_MUTEX = 2,
    SEMAPHORE_COUNT = 3
};

typedef enum {
    RING_RECORD,
    RING_DONE
} ring_message_type_t;

typedef struct {
    ring_message_type_t type;
    record_t record;
    uint32_t producer_id;
} ring_message_t;

typedef struct {
    size_t head;
    size_t tail;
    ring_message_t slots[];
} shared_ring_t;

typedef enum {
    SEMAPHORE_WAIT_ACQUIRED,
    SEMAPHORE_WAIT_TIMEOUT,
    SEMAPHORE_WAIT_ERROR
} semaphore_wait_result_t;

union semun {
    int val;
    struct semid_ds *buf;
    unsigned short *array;
    struct seminfo *__buf;
};

static bool allocation_size_is_valid(size_t count, size_t element_size) {
    return count <= SIZE_MAX / element_size;
}

static bool ring_size_is_valid(size_t capacity) {
    const size_t header_size = offsetof(shared_ring_t, slots);

    return capacity <= (SIZE_MAX - header_size) / sizeof(ring_message_t);
}

static bool semaphore_operation(
    int semaphore_id,
    unsigned short semaphore_number,
    short operation
) {
    struct sembuf action = {semaphore_number, operation, 0};
    int status;

    do {
        status = runtime_semop(semaphore_id, &action, 1);
    } while (status < 0 && errno == EINTR);

    return status == 0;
}

static semaphore_wait_result_t wait_for_full(int semaphore_id) {
    struct sembuf action = {SEMAPHORE_FULL, -1, 0};

    while (!runtime_cancelled()) {
        const struct timespec timeout = {0, 100000000};

        if (semtimedop(semaphore_id, &action, 1, &timeout) == 0) {
            return SEMAPHORE_WAIT_ACQUIRED;
        }

        if (errno == EINTR) {
            continue;
        }
        if (errno == EAGAIN) {
            return SEMAPHORE_WAIT_TIMEOUT;
        }
        return SEMAPHORE_WAIT_ERROR;
    }
    return SEMAPHORE_WAIT_ERROR;
}

static size_t advance_index(size_t index, size_t capacity) {
    ++index;
    if (index == capacity) {
        index = 0;
    }
    return index;
}

static bool send_message(
    int semaphore_id,
    shared_ring_t *ring,
    size_t capacity,
    const ring_message_t *message
) {
    if (!semaphore_operation(semaphore_id, SEMAPHORE_EMPTY, -1)) {
        return false;
    }
    if (!semaphore_operation(
            semaphore_id,
            SEMAPHORE_PRODUCER_MUTEX,
            -1
        )) {
        return false;
    }

    runtime_child_fault();
    ring->slots[ring->tail] = *message;
    ring->tail = advance_index(ring->tail, capacity);

    if (!semaphore_operation(
            semaphore_id,
            SEMAPHORE_PRODUCER_MUTEX,
            1
        )) {
        return false;
    }

    return semaphore_operation(semaphore_id, SEMAPHORE_FULL, 1);
}

static bool child_exited_successfully(int status) {
    return WIFEXITED(status) && WEXITSTATUS(status) == 0;
}

static bool reap_exited_children(
    uint32_t children_created,
    uint32_t *children_reaped,
    bool *child_failed
) {
    while (*children_reaped < children_created) {
        int status;
        pid_t waited;

        do {
            waited = runtime_wait(&status, WNOHANG);
        } while (waited < 0 && errno == EINTR);

        if (waited < 0) {
            return false;
        }
        if (waited == 0) {
            return true;
        }

        ++*children_reaped;
        if (!child_exited_successfully(status)) {
            *child_failed = true;
        }
    }

    return true;
}

static bool reap_remaining_children(
    uint32_t children_created,
    uint32_t *children_reaped
) {
    bool succeeded = true;

    while (*children_reaped < children_created) {
        int status;
        pid_t waited;

        do {
            waited = runtime_wait(&status, 0);
        } while (waited < 0 && errno == EINTR);

        if (waited < 0) {
            return false;
        }

        ++*children_reaped;
        if (!child_exited_successfully(status)) {
            succeeded = false;
        }
    }

    return succeeded && !runtime_cancelled();
}

bool ipc_run_shm_ring(
    const ipc_ring_config_t *config,
    ipc_result_t *result
) {
    validator_t validator;
    validation_result_t validation;
    shared_ring_t *ring = (void *) -1;
    bool *producer_done = NULL;
    timestamp_t start;
    timestamp_t end;
    size_t capacity;
    size_t ring_size;
    double elapsed_seconds = 0.0;
    int shared_memory_id = -1;
    int semaphore_id = -1;
    uint32_t children_created = 0;
    uint32_t children_reaped = 0;
    uint32_t done_count = 0;
    bool succeeded = true;
    union semun semaphore_value;

    if (!result) {
        return false;
    }

    *result = (ipc_result_t) {0};

    if (!config) {
        return false;
    }

    if (config->producers == 0 ||
        config->records_per_producer == 0 ||
        config->capacity == 0) {
        return false;
    }

    if (config->records_per_producer > UINT64_MAX / config->producers) {
        return false;
    }

    if (!runtime_begin(config->producers)) {
        return false;
    }

    if (!validator_init(
            &validator,
            config->producers,
            config->records_per_producer
        )) {
        return false;
    }

    if (!allocation_size_is_valid(
            config->producers,
            sizeof(*producer_done)
        )) {
        validator_destroy(&validator);
        return false;
    }

    producer_done = calloc(
        (size_t) config->producers,
        sizeof(*producer_done)
    );
    if (!producer_done) {
        validator_destroy(&validator);
        return false;
    }

    capacity = (size_t) config->capacity;
    if (!ring_size_is_valid(capacity)) {
        free(producer_done);
        validator_destroy(&validator);
        return false;
    }
    ring_size = offsetof(shared_ring_t, slots)
        + capacity * sizeof(ring_message_t);

    shared_memory_id = shmget(
        IPC_PRIVATE,
        ring_size,
        IPC_CREAT | 0600
    );
#ifdef IPC_TESTING
    fprintf(stderr, "owned_shm=%d\n", shared_memory_id);
#endif
    if (shared_memory_id < 0) {
        free(producer_done);
        validator_destroy(&validator);
        return false;
    }

    ring = shmat(shared_memory_id, NULL, 0);
    if (ring == (void *) -1) {
        shmctl(shared_memory_id, IPC_RMID, NULL);
        free(producer_done);
        validator_destroy(&validator);
        return false;
    }
    ring->head = 0;
    ring->tail = 0;

    semaphore_id = semget(
        IPC_PRIVATE,
        SEMAPHORE_COUNT,
        IPC_CREAT | 0600
    );
#ifdef IPC_TESTING
    fprintf(stderr, "owned_sem=%d\n", semaphore_id);
#endif
    if (semaphore_id < 0) {
        shmdt(ring);
        shmctl(shared_memory_id, IPC_RMID, NULL);
        free(producer_done);
        validator_destroy(&validator);
        return false;
    }

    if (config->capacity > INT_MAX) {
        succeeded = false;
    }

    semaphore_value.val = (int) config->capacity;
    if (succeeded && semctl(
            semaphore_id,
            SEMAPHORE_EMPTY,
            SETVAL,
            semaphore_value
        ) < 0) {
        succeeded = false;
    }

    semaphore_value.val = 0;
    if (succeeded && semctl(
            semaphore_id,
            SEMAPHORE_FULL,
            SETVAL,
            semaphore_value
        ) < 0) {
        succeeded = false;
    }

    semaphore_value.val = 1;
    if (succeeded && semctl(
            semaphore_id,
            SEMAPHORE_PRODUCER_MUTEX,
            SETVAL,
            semaphore_value
        ) < 0) {
        succeeded = false;
    }

    if (succeeded && !timing_now(&start)) {
        succeeded = false;
    }

    if (succeeded) {
        for (uint32_t producer = 0; producer < config->producers; ++producer) {
            pid_t child = runtime_fork();

            if (child < 0) {
                succeeded = false;
                break;
            }

            if (child == 0) {
                ring_message_t message = {0};

                for (uint64_t sequence = 0;
                     sequence < config->records_per_producer;
                     ++sequence) {
                    message.type = RING_RECORD;
                    message.record = record_make(producer, sequence);

                    if (!send_message(
                            semaphore_id,
                            ring,
                            capacity,
                            &message
                        )) {
                        shmdt(ring);
                        _exit(1);
                    }
                }

                message.type = RING_DONE;
                message.producer_id = producer;
                if (!send_message(
                        semaphore_id,
                        ring,
                        capacity,
                        &message
                    )) {
                    shmdt(ring);
                    _exit(1);
                }

                if (shmdt(ring) != 0) {
                    _exit(1);
                }
                _exit(0);
            }

            ++children_created;
        }
    }

    while (succeeded && done_count < config->producers) {
        runtime_consumer_delay();
        semaphore_wait_result_t wait_result = wait_for_full(semaphore_id);

        if (wait_result == SEMAPHORE_WAIT_TIMEOUT) {
            bool child_failed = false;

            if (!reap_exited_children(
                    children_created,
                    &children_reaped,
                    &child_failed
                ) || child_failed) {
                succeeded = false;
            } else if (children_reaped == children_created &&
                       done_count < config->producers) {
                succeeded = false;
            }
            continue;
        }

        if (wait_result == SEMAPHORE_WAIT_ERROR) {
            succeeded = false;
            break;
        }

        {
            ring_message_t message = ring->slots[ring->head];

            ring->head = advance_index(ring->head, capacity);

            if (!semaphore_operation(semaphore_id, SEMAPHORE_EMPTY, 1)) {
                succeeded = false;
                break;
            }

            if (message.type == RING_RECORD) {
                validator_observe(&validator, &message.record);
            } else if (message.type == RING_DONE) {
                if (message.producer_id >= config->producers ||
                    producer_done[message.producer_id]) {
                    succeeded = false;
                } else {
                    producer_done[message.producer_id] = true;
                    ++done_count;
                }
            } else {
                succeeded = false;
            }
        }
    }

    if (succeeded && !reap_remaining_children(
            children_created,
            &children_reaped
        )) {
        succeeded = false;
    }

    if (succeeded && !timing_now(&end)) {
        succeeded = false;
    }

    if (succeeded) {
        validation = validator_finish(&validator);
        elapsed_seconds = timing_elapsed_seconds(&start, &end);
    }

    if (!succeeded) {
        runtime_cancel();
    }

    if (!succeeded && semaphore_id >= 0) {
        if (semctl(semaphore_id, 0, IPC_RMID) == 0) {
            semaphore_id = -1;
        }
    }

    if (!reap_remaining_children(children_created, &children_reaped)) {
        succeeded = false;
    }

    if (semaphore_id >= 0 && semctl(semaphore_id, 0, IPC_RMID) < 0) {
        succeeded = false;
    }
    if (shmdt(ring) != 0) {
        succeeded = false;
    }
    if (shmctl(shared_memory_id, IPC_RMID, NULL) != 0) {
        succeeded = false;
    }

    if (succeeded) {
        result->validation = validation;
        result->elapsed_seconds = elapsed_seconds;
        if (elapsed_seconds > 0.0) {
            result->records_per_second =
                (double) validation.received / elapsed_seconds;
        }
    }

    free(producer_done);
    validator_destroy(&validator);
    return succeeded && !runtime_cancelled();
}
