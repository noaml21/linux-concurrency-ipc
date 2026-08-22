#include <assert.h>
#include <stdint.h>
#include <stdio.h>

#include "ipc.h"

static void set_nonzero_result(ipc_result_t *result) {
    result->validation.expected = 1;
    result->validation.received = 1;
    result->validation.missing = 1;
    result->validation.duplicates = 1;
    result->validation.corrupted = 1;
    result->validation.out_of_range = 1;
    result->validation.pass = true;
    result->elapsed_seconds = 1.0;
    result->records_per_second = 1.0;
}

static void assert_zero_result(const ipc_result_t *result) {
    assert(result->validation.expected == 0);
    assert(result->validation.received == 0);
    assert(result->validation.missing == 0);
    assert(result->validation.duplicates == 0);
    assert(result->validation.corrupted == 0);
    assert(result->validation.out_of_range == 0);
    assert(!result->validation.pass);
    assert(result->elapsed_seconds == 0.0);
    assert(result->records_per_second == 0.0);
}

static void assert_successful_result(
    const ipc_result_t *result,
    uint64_t expected
) {
    assert(result->validation.pass);
    assert(result->validation.expected == expected);
    assert(result->validation.received == expected);
    assert(result->validation.missing == 0);
    assert(result->validation.duplicates == 0);
    assert(result->validation.corrupted == 0);
    assert(result->validation.out_of_range == 0);
    assert(result->elapsed_seconds >= 0.0);
    assert(result->records_per_second >= 0.0);
}

static void test_invalid_inputs(void) {
    const ipc_ring_config_t valid = {1, 1, 1};
    const ipc_ring_config_t no_producers = {0, 1, 1};
    const ipc_ring_config_t no_records = {1, 0, 1};
    const ipc_ring_config_t no_capacity = {1, 1, 0};
    const ipc_ring_config_t overflow = {2, UINT64_MAX, 1};
    ipc_result_t result;

    set_nonzero_result(&result);
    assert(!ipc_run_shm_ring(NULL, &result));
    assert_zero_result(&result);

    assert(!ipc_run_shm_ring(&valid, NULL));

    set_nonzero_result(&result);
    assert(!ipc_run_shm_ring(&no_producers, &result));
    assert_zero_result(&result);

    set_nonzero_result(&result);
    assert(!ipc_run_shm_ring(&no_records, &result));
    assert_zero_result(&result);

    set_nonzero_result(&result);
    assert(!ipc_run_shm_ring(&no_capacity, &result));
    assert_zero_result(&result);

    set_nonzero_result(&result);
    assert(!ipc_run_shm_ring(&overflow, &result));
    assert_zero_result(&result);
}

static void test_capacity_one(void) {
    const ipc_ring_config_t config = {1, 1000, 1};
    ipc_result_t result;

    assert(ipc_run_shm_ring(&config, &result));
    assert_successful_result(&result, 1000);
}

static void test_small_ring(void) {
    const ipc_ring_config_t config = {4, 5000, 8};
    ipc_result_t result;

    assert(ipc_run_shm_ring(&config, &result));
    assert_successful_result(&result, 20000);
}

static void test_larger_ring(void) {
    const ipc_ring_config_t config = {4, 5000, 256};
    ipc_result_t result;

    assert(ipc_run_shm_ring(&config, &result));
    assert_successful_result(&result, 20000);
}

int main(void) {
    test_invalid_inputs();
    test_capacity_one();
    test_small_ring();
    test_larger_ring();

    printf("test_shm_ring: PASS\n");
    return 0;
}
