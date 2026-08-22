#include <assert.h>
#include <stdint.h>
#include <stdio.h>

#include "record.h"

int main(void) {
    const uint32_t producer_id = 3;
    const uint64_t sequence = 17;
    const record_t record = record_make(producer_id, sequence);
    record_t corrupted = record;
    const uint64_t first_value = record_value(3, 17);
    const uint64_t second_value = record_value(3, 17);

    corrupted.value ^= UINT64_C(1);

    assert(record.producer_id == producer_id);
    assert(record.sequence == sequence);
    assert(record.value == record_value(3, 17));
    assert(first_value == second_value);
    assert(first_value == UINT64_C(0x36f110294aaa12e5));
    assert(record_value(0, 0) != 0);
    assert(record_is_valid(&record));
    assert(!record_is_valid(&corrupted));
    assert(!record_is_valid(NULL));

    printf("test_record: PASS\n");
    return 0;
}
