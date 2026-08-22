#ifndef SYNC_H
#define SYNC_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    uint32_t workers;
    uint64_t operations_per_worker;
} sync_config_t;

typedef struct {
    uint64_t expected;
    uint64_t observed;
    double elapsed_seconds;
    double operations_per_second;
} sync_result_t;

bool sync_run_process_unsafe(
    const sync_config_t *config,
    sync_result_t *result
);

bool sync_run_threads_mutex(
    const sync_config_t *config,
    sync_result_t *result
);

bool sync_run_process_sem(
    const sync_config_t *config,
    sync_result_t *result
);

#endif
