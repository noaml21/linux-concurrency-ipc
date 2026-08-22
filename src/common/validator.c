#include "validator.h"

#include <stdlib.h>
#include <string.h>

bool validator_init(
    validator_t *validator,
    uint32_t producer_count,
    uint64_t records_per_producer
) {
    uint64_t expected;

    if (!validator) {
        return false;
    }

    memset(validator, 0, sizeof(*validator));

    if (producer_count == 0 || records_per_producer == 0) {
        return false;
    }

    if (records_per_producer > UINT64_MAX / producer_count) {
        return false;
    }

    expected = (uint64_t) producer_count * records_per_producer;
    if (expected > SIZE_MAX) {
        return false;
    }

    validator->producer_count = producer_count;
    validator->records_per_producer = records_per_producer;
    validator->expected = expected;
    validator->seen = calloc((size_t) expected, sizeof(*validator->seen));
    if (!validator->seen) {
        return false;
    }

    return true;
}

void validator_observe(
    validator_t *validator,
    const record_t *record
) {
    uint64_t index;

    if (!validator || !validator->seen || !record) {
        return;
    }

    ++validator->received;

    if (record->producer_id >= validator->producer_count
        || record->sequence >= validator->records_per_producer) {
        ++validator->out_of_range;
        return;
    }

    index = (uint64_t) record->producer_id * validator->records_per_producer
        + record->sequence;

    if (validator->seen[(size_t) index]) {
        ++validator->duplicates;
    } else {
        validator->seen[(size_t) index] = 1;
        ++validator->unique;
    }

    if (!record_is_valid(record)) {
        ++validator->corrupted;
    }
}

validation_result_t validator_finish(
    const validator_t *validator
) {
    validation_result_t result = {0};

    if (!validator) {
        return result;
    }

    result.expected = validator->expected;
    result.received = validator->received;
    result.missing = validator->expected - validator->unique;
    result.duplicates = validator->duplicates;
    result.corrupted = validator->corrupted;
    result.out_of_range = validator->out_of_range;
    result.pass = result.received == result.expected
        && result.missing == 0
        && result.duplicates == 0
        && result.corrupted == 0
        && result.out_of_range == 0;

    return result;
}

void validator_destroy(
    validator_t *validator
) {
    if (!validator) {
        return;
    }

    free(validator->seen);
    memset(validator, 0, sizeof(*validator));
}
