#ifndef VALIDATOR_H
#define VALIDATOR_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "record.h"

typedef struct {
    uint32_t producer_count;
    uint64_t records_per_producer;
    uint64_t expected;
    uint64_t received;
    uint64_t unique;
    uint64_t duplicates;
    uint64_t corrupted;
    uint64_t out_of_range;
    uint8_t *seen;
} validator_t;

typedef struct {
    uint64_t expected;
    uint64_t received;
    uint64_t missing;
    uint64_t duplicates;
    uint64_t corrupted;
    uint64_t out_of_range;
    bool pass;
} validation_result_t;

bool validator_init(
    validator_t *validator,
    uint32_t producer_count,
    uint64_t records_per_producer
);

void validator_observe(
    validator_t *validator,
    const record_t *record
);

validation_result_t validator_finish(
    const validator_t *validator
);

void validator_destroy(
    validator_t *validator
);

#endif
