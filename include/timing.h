#ifndef TIMING_H
#define TIMING_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    int64_t seconds;
    int64_t nanoseconds;
} timestamp_t;

bool timing_now(timestamp_t *timestamp);

double timing_elapsed_seconds(
    const timestamp_t *start,
    const timestamp_t *end
);

#endif
