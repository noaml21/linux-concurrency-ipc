#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "ipc.h"
#include "sync.h"

static void print_usage(FILE *stream, const char *program_name) {
    fprintf(
        stream,
        "Usage:\n"
        "  %s --help\n"
        "  %s sync process-unsafe <workers> <operations_per_worker>\n"
        "  %s sync threads-mutex <workers> <operations_per_worker>\n"
        "  %s sync process-sem <workers> <operations_per_worker>\n"
        "  %s ipc pipe <producers> <records_per_producer>\n"
        "  %s ipc fifo <producers> <records_per_producer>\n"
        "  %s ipc shm-mailbox <producers> <records_per_producer>\n"
        "  %s ipc shm-ring <producers> <records_per_producer> <capacity>\n",
        program_name,
        program_name,
        program_name,
        program_name,
        program_name,
        program_name,
        program_name,
        program_name
    );
}

static bool contains_only_decimal_digits(const char *text) {
    const unsigned char *current = (const unsigned char *) text;

    if (!text || *text == '\0') {
        return false;
    }

    while (*current != '\0') {
        if (*current < (unsigned char) '0' ||
            *current > (unsigned char) '9') {
            return false;
        }
        ++current;
    }

    return true;
}

static bool parse_uint32_positive(const char *text, uint32_t *value) {
    char *end;
    unsigned long parsed;

    if (!value || !contains_only_decimal_digits(text)) {
        return false;
    }

    errno = 0;
    parsed = strtoul(text, &end, 10);
    if (errno == ERANGE || *end != '\0' || parsed == 0 ||
        parsed > UINT32_MAX) {
        return false;
    }

    *value = (uint32_t) parsed;
    return true;
}

static bool parse_uint64_positive(const char *text, uint64_t *value) {
    char *end;
    unsigned long long parsed;

    if (!value || !contains_only_decimal_digits(text)) {
        return false;
    }

    errno = 0;
    parsed = strtoull(text, &end, 10);
    if (errno == ERANGE || *end != '\0' || parsed == 0) {
        return false;
    }

#if ULLONG_MAX > UINT64_MAX
    if (parsed > UINT64_MAX) {
        return false;
    }
#endif

    *value = (uint64_t) parsed;
    return true;
}

static int run_sync_command(
    const char *mode,
    const sync_config_t *config
) {
    sync_result_t result;
    uint64_t lost_updates;
    bool succeeded;

    if (strcmp(mode, "process-unsafe") == 0) {
        succeeded = sync_run_process_unsafe(config, &result);
    } else if (strcmp(mode, "threads-mutex") == 0) {
        succeeded = sync_run_threads_mutex(config, &result);
    } else {
        succeeded = sync_run_process_sem(config, &result);
    }

    if (!succeeded) {
        fprintf(stderr, "error: synchronization experiment failed\n");
        return 1;
    }

    if (result.observed > result.expected) {
        fprintf(stderr, "error: observed count exceeds expected count\n");
        return 1;
    }
    lost_updates = result.expected - result.observed;

    printf(
        "family=sync mode=%s workers=%" PRIu32
        " operations_per_worker=%" PRIu64
        " expected=%" PRIu64
        " observed=%" PRIu64
        " lost_updates=%" PRIu64
        " elapsed_seconds=%.6f operations_per_second=%.6f\n",
        mode,
        config->workers,
        config->operations_per_worker,
        result.expected,
        result.observed,
        lost_updates,
        result.elapsed_seconds,
        result.operations_per_second
    );

    return 0;
}

static void print_ipc_result(
    const char *mode,
    uint32_t producers,
    uint64_t records_per_producer,
    bool include_capacity,
    uint32_t capacity,
    const ipc_result_t *result
) {
    printf(
        "family=ipc mode=%s producers=%" PRIu32
        " records_per_producer=%" PRIu64,
        mode,
        producers,
        records_per_producer
    );

    if (include_capacity) {
        printf(" capacity=%" PRIu32, capacity);
    }

    printf(
        " expected=%" PRIu64
        " received=%" PRIu64
        " missing=%" PRIu64
        " duplicates=%" PRIu64
        " corrupted=%" PRIu64
        " out_of_range=%" PRIu64
        " validation_pass=%d"
        " elapsed_seconds=%.6f records_per_second=%.6f\n",
        result->validation.expected,
        result->validation.received,
        result->validation.missing,
        result->validation.duplicates,
        result->validation.corrupted,
        result->validation.out_of_range,
        result->validation.pass ? 1 : 0,
        result->elapsed_seconds,
        result->records_per_second
    );
}

static int run_ipc_command(
    const char *mode,
    uint32_t producers,
    uint64_t records_per_producer,
    uint32_t capacity
) {
    ipc_result_t result;
    bool succeeded;

    if (strcmp(mode, "shm-ring") == 0) {
        const ipc_ring_config_t config = {
            producers,
            records_per_producer,
            capacity
        };

        succeeded = ipc_run_shm_ring(&config, &result);
    } else {
        const ipc_config_t config = {producers, records_per_producer};

        if (strcmp(mode, "pipe") == 0) {
            succeeded = ipc_run_pipe(&config, &result);
        } else if (strcmp(mode, "fifo") == 0) {
            succeeded = ipc_run_fifo(&config, &result);
        } else {
            succeeded = ipc_run_shm_mailbox(&config, &result);
        }
    }

    if (!succeeded) {
        fprintf(stderr, "error: IPC experiment failed\n");
        return 1;
    }

    print_ipc_result(
        mode,
        producers,
        records_per_producer,
        strcmp(mode, "shm-ring") == 0,
        capacity,
        &result
    );
    return 0;
}

int main(int argc, char **argv) {
    if (argc == 2 && strcmp(argv[1], "--help") == 0) {
        print_usage(stdout, argv[0]);
        return 0;
    }

    if (argc >= 2 && strcmp(argv[1], "sync") == 0) {
        sync_config_t config;

        if (argc != 5 ||
            (strcmp(argv[2], "process-unsafe") != 0 &&
             strcmp(argv[2], "threads-mutex") != 0 &&
             strcmp(argv[2], "process-sem") != 0) ||
            !parse_uint32_positive(argv[3], &config.workers) ||
            !parse_uint64_positive(
                argv[4],
                &config.operations_per_worker
            )) {
            print_usage(stderr, argv[0]);
            return 2;
        }

        return run_sync_command(argv[2], &config);
    }

    if (argc >= 2 && strcmp(argv[1], "ipc") == 0) {
        uint32_t producers;
        uint64_t records_per_producer;
        uint32_t capacity = 0;

        if (argc < 3 ||
            (strcmp(argv[2], "pipe") != 0 &&
             strcmp(argv[2], "fifo") != 0 &&
             strcmp(argv[2], "shm-mailbox") != 0 &&
             strcmp(argv[2], "shm-ring") != 0) ||
            (strcmp(argv[2], "shm-ring") == 0 && argc != 6) ||
            (strcmp(argv[2], "shm-ring") != 0 && argc != 5) ||
            !parse_uint32_positive(argv[3], &producers) ||
            !parse_uint64_positive(argv[4], &records_per_producer) ||
            (strcmp(argv[2], "shm-ring") == 0 &&
             !parse_uint32_positive(argv[5], &capacity))) {
            print_usage(stderr, argv[0]);
            return 2;
        }

        return run_ipc_command(
            argv[2],
            producers,
            records_per_producer,
            capacity
        );
    }

    print_usage(stderr, argv[0]);
    return 2;
}
