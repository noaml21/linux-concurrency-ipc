#include "record.h"

uint64_t record_value(uint32_t producer_id, uint64_t sequence) {
    uint64_t x = sequence
        ^ ((uint64_t) producer_id << 32)
        ^ UINT64_C(0x9e3779b97f4a7c15);

    x ^= x >> 30;
    x *= UINT64_C(0xbf58476d1ce4e5b9);
    x ^= x >> 27;
    x *= UINT64_C(0x94d049bb133111eb);
    x ^= x >> 31;

    return x;
}

record_t record_make(uint32_t producer_id, uint64_t sequence) {
    record_t record = {
        .sequence = sequence,
        .producer_id = producer_id,
        .value = record_value(producer_id, sequence),
    };

    return record;
}

bool record_is_valid(const record_t *record) {
    if (!record) {
        return false;
    }

    return record->value == record_value(record->producer_id, record->sequence);
}
