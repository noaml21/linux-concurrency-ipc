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

static void test_invalid_inputs(void) {
    const ipc_config_t valid = {1, 1};
    const ipc_config_t no_producers = {0, 1};
    const ipc_config_t no_records = {1, 0};
    const ipc_config_t overflow = {2, UINT64_MAX};
    ipc_result_t result;

    set_nonzero_result(&result);
    assert(!ipc_run_pipe(NULL, &result));
    assert_zero_result(&result);

    assert(!ipc_run_pipe(&valid, NULL));

    set_nonzero_result(&result);
    assert(!ipc_run_pipe(&no_producers, &result));
    assert_zero_result(&result);

    set_nonzero_result(&result);
    assert(!ipc_run_pipe(&no_records, &result));
    assert_zero_result(&result);

    set_nonzero_result(&result);
    assert(!ipc_run_pipe(&overflow, &result));
    assert_zero_result(&result);
}

static void test_single_producer(void) {
    const ipc_config_t config = {1, 1000};
    ipc_result_t result;

    assert(ipc_run_pipe(&config, &result));
    assert(result.validation.pass);
    assert(result.validation.expected == 1000);
    assert(result.validation.received == 1000);
    assert(result.validation.missing == 0);
    assert(result.validation.duplicates == 0);
    assert(result.validation.corrupted == 0);
    assert(result.validation.out_of_range == 0);
    assert(result.elapsed_seconds >= 0.0);
    assert(result.records_per_second >= 0.0);
}

static void test_multiple_producers(void) {
    const ipc_config_t config = {4, 5000};
    ipc_result_t result;

    assert(ipc_run_pipe(&config, &result));
    assert(result.validation.pass);
    assert(result.validation.expected == 20000);
    assert(result.validation.received == 20000);
    assert(result.validation.missing == 0);
    assert(result.validation.duplicates == 0);
    assert(result.validation.corrupted == 0);
    assert(result.validation.out_of_range == 0);
    assert(result.elapsed_seconds >= 0.0);
    assert(result.records_per_second >= 0.0);
}

int main(void) {
    test_invalid_inputs();
    test_single_producer();
    test_multiple_producers();

    printf("test_pipe: PASS\n");
    return 0;
}
