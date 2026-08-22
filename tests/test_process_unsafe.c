#include <assert.h>
#include <stdint.h>
#include <stdio.h>

#include "sync.h"

static void test_invalid_inputs(void) {
    const sync_config_t valid = {1, 1};
    const sync_config_t no_workers = {0, 1};
    const sync_config_t no_operations = {1, 0};
    const sync_config_t overflow = {2, UINT64_MAX};
    sync_result_t result;

    result.expected = 1;
    result.observed = 1;
    result.elapsed_seconds = 1.0;
    result.operations_per_second = 1.0;
    assert(!sync_run_process_unsafe(NULL, &result));
    assert(result.expected == 0);
    assert(result.observed == 0);
    assert(result.elapsed_seconds == 0.0);
    assert(result.operations_per_second == 0.0);
    assert(!sync_run_process_unsafe(&valid, NULL));
    assert(!sync_run_process_unsafe(&no_workers, &result));
    assert(!sync_run_process_unsafe(&no_operations, &result));
    assert(!sync_run_process_unsafe(&overflow, &result));
}

static void test_single_worker(void) {
    const sync_config_t config = {1, 1000};
    sync_result_t result;

    assert(sync_run_process_unsafe(&config, &result));
    assert(result.expected == 1000);
    assert(result.observed == 1000);
    assert(result.elapsed_seconds >= 0.0);
    assert(result.operations_per_second >= 0.0);
}

static void test_multiple_workers(void) {
    const sync_config_t config = {4, 10000};
    sync_result_t result;

    assert(sync_run_process_unsafe(&config, &result));
    assert(result.expected == 40000);
    assert(result.observed > 0);
    assert(result.observed <= result.expected);
    assert(result.elapsed_seconds >= 0.0);
}

int main(void) {
    test_invalid_inputs();
    test_single_worker();
    test_multiple_workers();

    printf("test_process_unsafe: PASS\n");
    return 0;
}
