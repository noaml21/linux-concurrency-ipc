#define _GNU_SOURCE

#include "sync.h"

#include <errno.h>
#include <stdint.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#include "timing.h"
#include "runtime.h"

bool sync_run_process_unsafe(
    const sync_config_t *config,
    sync_result_t *result
) {
    volatile uint64_t *counter;
    timestamp_t start;
    timestamp_t end;
    uint64_t expected;
    uint32_t children_created = 0;
    bool succeeded = true;

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

    if (!timing_now(&start)) {
        munmap((void *) counter, sizeof(*counter));
        return false;
    }

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
                if (runtime_cancelled()) {
                    _exit(1);
                }
                runtime_child_fault();
                uint64_t value = *counter;

                *counter = value + 1;
            }
            _exit(0);
        }

        ++children_created;
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
        result->expected = expected;
        result->observed = *counter;
        result->elapsed_seconds = timing_elapsed_seconds(&start, &end);
        if (result->elapsed_seconds > 0.0) {
            result->operations_per_second =
                (double) expected / result->elapsed_seconds;
        }
    }

    if (munmap((void *) counter, sizeof(*counter)) != 0) {
        return false;
    }

    return succeeded && !runtime_cancelled();
}
