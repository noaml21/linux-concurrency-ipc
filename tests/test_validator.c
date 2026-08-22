#include <assert.h>
#include <stdio.h>

#include "validator.h"

static void test_complete_valid_input(void) {
    validator_t validator;
    validation_result_t result;

    assert(validator_init(&validator, 2, 3));

    for (uint32_t producer_id = 0; producer_id < 2; ++producer_id) {
        for (uint64_t sequence = 0; sequence < 3; ++sequence) {
            const record_t record = record_make(producer_id, sequence);
            validator_observe(&validator, &record);
        }
    }

    result = validator_finish(&validator);
    assert(result.pass);
    assert(result.expected == 6);
    assert(result.received == 6);
    assert(result.missing == 0);
    assert(result.duplicates == 0);
    assert(result.corrupted == 0);
    assert(result.out_of_range == 0);

    validator_destroy(&validator);
}

static void test_error_detection(void) {
    validator_t validator;
    validation_result_t result;
    record_t record;

    assert(validator_init(&validator, 2, 3));

    record = record_make(0, 0);
    validator_observe(&validator, &record);

    record = record_make(0, 1);
    validator_observe(&validator, &record);
    validator_observe(&validator, &record);

    record = record_make(0, 2);
    record.value ^= UINT64_C(1);
    validator_observe(&validator, &record);

    record = record_make(1, 0);
    validator_observe(&validator, &record);

    record = record_make(1, 1);
    validator_observe(&validator, &record);

    record = record_make(2, 0);
    validator_observe(&validator, &record);

    result = validator_finish(&validator);
    assert(!result.pass);
    assert(result.expected == 6);
    assert(result.received == 7);
    assert(result.missing == 1);
    assert(result.duplicates == 1);
    assert(result.corrupted == 1);
    assert(result.out_of_range == 1);

    validator_destroy(&validator);
}

static void test_initialization_validation(void) {
    validator_t validator;

    assert(!validator_init(&validator, 0, 3));
    assert(!validator_init(&validator, 2, 0));
    assert(!validator_init(NULL, 2, 3));
    assert(!validator_init(&validator, UINT32_MAX, UINT64_MAX));
}

int main(void) {
    test_complete_valid_input();
    test_error_detection();
    test_initialization_validation();

    printf("test_validator: PASS\n");
    return 0;
}
