#ifndef RECORD_H
#define RECORD_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    uint64_t sequence;
    uint32_t producer_id;
    uint64_t value;
} record_t;

uint64_t record_value(uint32_t producer_id, uint64_t sequence);
record_t record_make(uint32_t producer_id, uint64_t sequence);
bool record_is_valid(const record_t *record);

#endif
