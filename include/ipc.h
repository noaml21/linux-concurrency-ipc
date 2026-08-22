#ifndef IPC_H
#define IPC_H

#include <stdbool.h>
#include <stdint.h>

#include "validator.h"

typedef struct {
    uint32_t producers;
    uint64_t records_per_producer;
} ipc_config_t;

typedef struct {
    validation_result_t validation;
    double elapsed_seconds;
    double records_per_second;
} ipc_result_t;

typedef struct {
    uint32_t producers;
    uint64_t records_per_producer;
    uint32_t capacity;
} ipc_ring_config_t;

bool ipc_run_pipe(
    const ipc_config_t *config,
    ipc_result_t *result
);

bool ipc_run_fifo(
    const ipc_config_t *config,
    ipc_result_t *result
);

bool ipc_run_shm_mailbox(
    const ipc_config_t *config,
    ipc_result_t *result
);

bool ipc_run_shm_ring(
    const ipc_ring_config_t *config,
    ipc_result_t *result
);

#endif
