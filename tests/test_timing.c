#include <assert.h>
#include <stdio.h>

#include "timing.h"

static void assert_approximately_equal(double actual, double expected) {
    const double tolerance = 0.000000001;

    assert(actual >= expected - tolerance);
    assert(actual <= expected + tolerance);
}

static void test_null_handling(void) {
    const timestamp_t valid = {0, 0};

    assert(!timing_now(NULL));
    assert(timing_elapsed_seconds(NULL, &valid) == 0.0);
    assert(timing_elapsed_seconds(&valid, NULL) == 0.0);
}

static void test_exact_synthetic_interval(void) {
    const timestamp_t start = {10, 200000000};
    const timestamp_t end = {12, 700000000};

    assert_approximately_equal(timing_elapsed_seconds(&start, &end), 2.5);
}

static void test_second_boundary(void) {
    const timestamp_t start = {5, 900000000};
    const timestamp_t end = {6, 100000000};

    assert_approximately_equal(timing_elapsed_seconds(&start, &end), 0.2);
}

static void test_negative_interval(void) {
    const timestamp_t start = {10, 500000000};
    const timestamp_t end = {9, 250000000};

    assert_approximately_equal(timing_elapsed_seconds(&start, &end), -1.25);
}

static void test_real_monotonic_clock(void) {
    timestamp_t start;
    timestamp_t end;

    assert(timing_now(&start));
    assert(timing_now(&end));
    assert(timing_elapsed_seconds(&start, &end) >= 0.0);
}

int main(void) {
    test_null_handling();
    test_exact_synthetic_interval();
    test_second_boundary();
    test_negative_interval();
    test_real_monotonic_clock();

    printf("test_timing: PASS\n");
    return 0;
}
