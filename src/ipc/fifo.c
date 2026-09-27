#define _POSIX_C_SOURCE 200809L

#include "ipc.h"

#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#include "io.h"
#include "record.h"
#include "timing.h"
#include "runtime.h"

_Static_assert(
    sizeof(record_t) <= PIPE_BUF,
    "record_t must fit within PIPE_BUF"
);

bool ipc_run_fifo(
    const ipc_config_t *config,
    ipc_result_t *result
) {
    char directory_template[] = "/tmp/linux-concurrency-ipc-XXXXXX";
    char fifo_path[PATH_MAX];
    validator_t validator;
    validation_result_t validation;
    timestamp_t start;
    timestamp_t end;
    record_t record;
    double elapsed_seconds = 0.0;
    int bootstrap_fd;
    int read_fd;
    int path_length;
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

    if (!mkdtemp(directory_template)) {
        validator_destroy(&validator);
        return false;
    }

    path_length = snprintf(
        fifo_path,
        sizeof(fifo_path),
        "%s/records.fifo",
        directory_template
    );
    if (path_length < 0 || (size_t) path_length >= sizeof(fifo_path)) {
        rmdir(directory_template);
        validator_destroy(&validator);
        return false;
    }

    if (mkfifo(fifo_path, 0600) != 0) {
        rmdir(directory_template);
        validator_destroy(&validator);
        return false;
    }

#ifdef IPC_TESTING
    fprintf(stderr, "owned_fifo=%s\n", fifo_path);
#endif
    bootstrap_fd = open(fifo_path, O_RDWR);
    if (bootstrap_fd < 0) {
        unlink(fifo_path);
        rmdir(directory_template);
        validator_destroy(&validator);
        return false;
    }

    read_fd = open(fifo_path, O_RDONLY);
    if (read_fd < 0) {
        close(bootstrap_fd);
        unlink(fifo_path);
        rmdir(directory_template);
        validator_destroy(&validator);
        return false;
    }

    if (!timing_now(&start)) {
        close(read_fd);
        close(bootstrap_fd);
        unlink(fifo_path);
        rmdir(directory_template);
        validator_destroy(&validator);
        return false;
    }

    for (uint32_t producer = 0; producer < config->producers; ++producer) {
        pid_t child = runtime_fork();

        if (child < 0) {
            succeeded = false;
            break;
        }

        if (child == 0) {
            int write_fd = open(fifo_path, O_WRONLY);

            if (write_fd < 0) {
                close(read_fd);
                close(bootstrap_fd);
                _exit(1);
            }

            if (close(bootstrap_fd) != 0) {
                close(read_fd);
                close(write_fd);
                _exit(1);
            }
            if (close(read_fd) != 0) {
                close(write_fd);
                _exit(1);
            }

            for (uint64_t sequence = 0;
                 sequence < config->records_per_producer;
                 ++sequence) {
                runtime_child_fault();
                record_t produced = record_make(producer, sequence);

                if (!write_all(write_fd, &produced, sizeof(produced))) {
                    close(write_fd);
                    _exit(1);
                }
            }

            if (close(write_fd) != 0) {
                _exit(1);
            }
            _exit(0);
        }

        ++children_created;
    }

    if (close(bootstrap_fd) != 0) {
        succeeded = false;
    }

    while (succeeded && !runtime_cancelled()) {
        runtime_consumer_delay();
        io_read_result_t read_result = read_full_or_eof(
            read_fd,
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

    if (close(read_fd) != 0) {
        succeeded = false;
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
        validation = validator_finish(&validator);
        elapsed_seconds = timing_elapsed_seconds(&start, &end);
    }

    if (unlink(fifo_path) != 0) {
        succeeded = false;
    }
    if (rmdir(directory_template) != 0) {
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

    validator_destroy(&validator);
    return succeeded && !runtime_cancelled();
}
