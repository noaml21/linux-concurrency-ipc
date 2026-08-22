#define _POSIX_C_SOURCE 200809L

#include "ipc.h"

#include <errno.h>
#include <limits.h>
#include <stdint.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#include "io.h"
#include "record.h"
#include "timing.h"

_Static_assert(
    sizeof(record_t) <= PIPE_BUF,
    "record_t must fit within PIPE_BUF"
);

bool ipc_run_pipe(
    const ipc_config_t *config,
    ipc_result_t *result
) {
    validator_t validator;
    timestamp_t start;
    timestamp_t end;
    record_t record;
    int pipe_fds[2];
    uint32_t children_created = 0;
    bool succeeded = true;

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

    if (pipe(pipe_fds) != 0) {
        validator_destroy(&validator);
        return false;
    }

    if (!timing_now(&start)) {
        close(pipe_fds[0]);
        close(pipe_fds[1]);
        validator_destroy(&validator);
        return false;
    }

    for (uint32_t producer = 0; producer < config->producers; ++producer) {
        pid_t child = fork();

        if (child < 0) {
            succeeded = false;
            break;
        }

        if (child == 0) {
            close(pipe_fds[0]);

            for (uint64_t sequence = 0;
                 sequence < config->records_per_producer;
                 ++sequence) {
                record_t produced = record_make(producer, sequence);

                if (!write_all(pipe_fds[1], &produced, sizeof(produced))) {
                    close(pipe_fds[1]);
                    _exit(1);
                }
            }

            close(pipe_fds[1]);
            _exit(0);
        }

        ++children_created;
    }

    if (close(pipe_fds[1]) != 0) {
        succeeded = false;
    }

    for (;;) {
        io_read_result_t read_result = read_full_or_eof(
            pipe_fds[0],
            &record,
            sizeof(record)
        );

        if (read_result == IO_READ_FULL) {
            validator_observe(&validator, &record);
            continue;
        }

        if (read_result == IO_READ_ERROR) {
            succeeded = false;
        }
        break;
    }

    if (close(pipe_fds[0]) != 0) {
        succeeded = false;
    }

    for (uint32_t child = 0; child < children_created; ++child) {
        int status;
        pid_t waited;

        do {
            waited = waitpid(-1, &status, 0);
        } while (waited < 0 && errno == EINTR);

        if (waited < 0 || !WIFEXITED(status) || WEXITSTATUS(status) != 0) {
            succeeded = false;
        }
    }

    if (succeeded && !timing_now(&end)) {
        succeeded = false;
    }

    if (succeeded) {
        result->validation = validator_finish(&validator);
        result->elapsed_seconds = timing_elapsed_seconds(&start, &end);
        if (result->elapsed_seconds > 0.0) {
            result->records_per_second =
                (double) result->validation.received /
                result->elapsed_seconds;
        }
    }

    validator_destroy(&validator);
    return succeeded;
}
