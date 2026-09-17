#define _GNU_SOURCE

#include "sync.h"

#include <errno.h>
#include <stdio.h>
#include <stdint.h>
#include <sys/ipc.h>
#include <sys/mman.h>
#include <sys/sem.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#include "timing.h"
#include "runtime.h"

union semun {
    int val;
    struct semid_ds *buf;
    unsigned short *array;
    struct seminfo *__buf;
};

static bool semaphore_operation(int semaphore_id, short operation) {
    struct sembuf action = {0, operation, SEM_UNDO};
    int status;

    do {
        status = runtime_semop(semaphore_id, &action, 1);
    } while (status < 0 && errno == EINTR);

    return status == 0;
}

static bool semaphore_acquire(int semaphore_id) {
    return semaphore_operation(semaphore_id, -1);
}

static bool semaphore_release(int semaphore_id) {
    return semaphore_operation(semaphore_id, 1);
}

bool sync_run_process_sem(
    const sync_config_t *config,
    sync_result_t *result
) {
    volatile uint64_t *counter;
    timestamp_t start;
    timestamp_t end;
    uint64_t expected;
    uint64_t observed = 0;
    double elapsed_seconds = 0.0;
    int semaphore_id;
    uint32_t children_created = 0;
    bool succeeded = true;
    union semun semaphore_value;

    if (!result) {
        return false;
    }

    *result = (sync_result_t) {0};

    if (!config) {
        return false;
    }

    if (config->workers == 0 || config->operations_per_worker == 0) {
        return false;
    }

    if (config->operations_per_worker > UINT64_MAX / config->workers) {
        return false;
    }
    if (!runtime_begin(config->workers)) {
        return false;
    }

    expected = (uint64_t) config->workers * config->operations_per_worker;

    counter = mmap(
        NULL,
        sizeof(*counter),
        PROT_READ | PROT_WRITE,
        MAP_SHARED | MAP_ANONYMOUS,
        -1,
        0
    );
    if (counter == MAP_FAILED) {
        return false;
    }
    *counter = 0;

    semaphore_id = semget(IPC_PRIVATE, 1, IPC_CREAT | 0600);
#ifdef IPC_TESTING
    fprintf(stderr, "owned_sem=%d\n", semaphore_id);
#endif
    if (semaphore_id < 0) {
        munmap((void *) counter, sizeof(*counter));
        return false;
    }

    semaphore_value.val = 1;
    if (semctl(semaphore_id, 0, SETVAL, semaphore_value) < 0) {
        semctl(semaphore_id, 0, IPC_RMID);
        munmap((void *) counter, sizeof(*counter));
        return false;
    }

    if (!timing_now(&start)) {
        succeeded = false;
    }

    if (succeeded) {
        for (uint32_t worker = 0; worker < config->workers; ++worker) {
            pid_t child = runtime_fork();

            if (child < 0) {
                succeeded = false;
                break;
            }

            if (child == 0) {
                for (uint64_t operation = 0;
                     operation < config->operations_per_worker;
                     ++operation) {
                    uint64_t value;

                    if (!semaphore_acquire(semaphore_id)) {
                        _exit(1);
                    }

                    runtime_child_fault();
                    value = *counter;
                    *counter = value + 1;

                    if (!semaphore_release(semaphore_id)) {
                        _exit(1);
                    }
                }
                _exit(0);
            }

            ++children_created;
        }
    }

    for (uint32_t child = 0; child < children_created; ++child) {
        int status;
        pid_t waited;

        do {
            waited = runtime_wait(&status, 0);
        } while (waited < 0 && errno == EINTR);

        if (waited < 0 || !WIFEXITED(status) || WEXITSTATUS(status) != 0) {
            succeeded = false;
        }
    }

    if (succeeded && !timing_now(&end)) {
        succeeded = false;
    }

    if (succeeded) {
        observed = *counter;
        if (observed != expected) {
            succeeded = false;
        } else {
            elapsed_seconds = timing_elapsed_seconds(&start, &end);
        }
    }

    if (semctl(semaphore_id, 0, IPC_RMID) < 0) {
        succeeded = false;
    }
    if (munmap((void *) counter, sizeof(*counter)) != 0) {
        succeeded = false;
    }

    if (succeeded) {
        result->expected = expected;
        result->observed = observed;
        result->elapsed_seconds = elapsed_seconds;
        if (elapsed_seconds > 0.0) {
            result->operations_per_second =
                (double) expected / elapsed_seconds;
        }
    }

    return succeeded && !runtime_cancelled();
}
