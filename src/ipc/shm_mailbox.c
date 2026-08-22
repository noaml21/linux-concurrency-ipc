#define _GNU_SOURCE

#include "ipc.h"

#include <errno.h>
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

enum {
    SEMAPHORE_EMPTY = 0,
    SEMAPHORE_FULL = 1,
    SEMAPHORE_COUNT = 2
};

typedef enum {
    MAILBOX_RECORD,
    MAILBOX_DONE
} mailbox_message_type_t;

typedef struct {
    mailbox_message_type_t type;
    record_t record;
    uint32_t producer_id;
} mailbox_message_t;

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

static bool semaphore_operation(
    int semaphore_id,
    unsigned short semaphore_number,
    short operation
) {
    struct sembuf action = {semaphore_number, operation, 0};
    int status;

    do {
        status = semop(semaphore_id, &action, 1);
    } while (status < 0 && errno == EINTR);

    return status == 0;
}

static semaphore_wait_result_t wait_for_full(int semaphore_id) {
    struct sembuf action = {SEMAPHORE_FULL, -1, 0};

    for (;;) {
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
}

static bool send_message(
    int semaphore_id,
    mailbox_message_t *shared_message,
    const mailbox_message_t *message
) {
    if (!semaphore_operation(semaphore_id, SEMAPHORE_EMPTY, -1)) {
        return false;
    }

    *shared_message = *message;

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
            waited = waitpid(-1, &status, WNOHANG);
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
            waited = waitpid(-1, &status, 0);
        } while (waited < 0 && errno == EINTR);

        if (waited < 0) {
            return false;
        }

        ++*children_reaped;
        if (!child_exited_successfully(status)) {
            succeeded = false;
        }
    }

    return succeeded;
}

bool ipc_run_shm_mailbox(
    const ipc_config_t *config,
    ipc_result_t *result
) {
    validator_t validator;
    validation_result_t validation;
    mailbox_message_t *shared_message = (void *) -1;
    bool *producer_done = NULL;
    timestamp_t start;
    timestamp_t end;
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

    if (config->producers == 0 || config->records_per_producer == 0) {
        return false;
    }

    if (config->records_per_producer > UINT64_MAX / config->producers) {
        return false;
    }

    if (!validator_init(
            &validator,
            config->producers,
            config->records_per_producer
        )) {
        return false;
    }

    shared_memory_id = shmget(
        IPC_PRIVATE,
        sizeof(*shared_message),
        IPC_CREAT | 0600
    );
    if (shared_memory_id < 0) {
        validator_destroy(&validator);
        return false;
    }

    shared_message = shmat(shared_memory_id, NULL, 0);
    if (shared_message == (void *) -1) {
        shmctl(shared_memory_id, IPC_RMID, NULL);
        validator_destroy(&validator);
        return false;
    }

    semaphore_id = semget(
        IPC_PRIVATE,
        SEMAPHORE_COUNT,
        IPC_CREAT | 0600
    );
    if (semaphore_id < 0) {
        shmdt(shared_message);
        shmctl(shared_memory_id, IPC_RMID, NULL);
        validator_destroy(&validator);
        return false;
    }

    semaphore_value.val = 1;
    if (semctl(
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

    if (!allocation_size_is_valid(
            config->producers,
            sizeof(*producer_done)
        )) {
        succeeded = false;
    }

    if (succeeded) {
        producer_done = calloc(
            (size_t) config->producers,
            sizeof(*producer_done)
        );
        if (!producer_done) {
            succeeded = false;
        }
    }

    if (succeeded && !timing_now(&start)) {
        succeeded = false;
    }

    if (succeeded) {
        for (uint32_t producer = 0; producer < config->producers; ++producer) {
            pid_t child = fork();

            if (child < 0) {
                succeeded = false;
                break;
            }

            if (child == 0) {
                mailbox_message_t message = {0};

                for (uint64_t sequence = 0;
                     sequence < config->records_per_producer;
                     ++sequence) {
                    message.type = MAILBOX_RECORD;
                    message.record = record_make(producer, sequence);

                    if (!send_message(
                            semaphore_id,
                            shared_message,
                            &message
                        )) {
                        shmdt(shared_message);
                        _exit(1);
                    }
                }

                message.type = MAILBOX_DONE;
                message.producer_id = producer;
                if (!send_message(semaphore_id, shared_message, &message)) {
                    shmdt(shared_message);
                    _exit(1);
                }

                if (shmdt(shared_message) != 0) {
                    _exit(1);
                }
                _exit(0);
            }

            ++children_created;
        }
    }

    while (succeeded && done_count < config->producers) {
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
            mailbox_message_t message = *shared_message;

            if (!semaphore_operation(
                    semaphore_id,
                    SEMAPHORE_EMPTY,
                    1
                )) {
                succeeded = false;
                break;
            }

            if (message.type == MAILBOX_RECORD) {
                validator_observe(&validator, &message.record);
            } else if (message.type == MAILBOX_DONE) {
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
    if (shmdt(shared_message) != 0) {
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
    return succeeded;
}
