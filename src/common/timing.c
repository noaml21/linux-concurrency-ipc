#define _POSIX_C_SOURCE 200809L

#include "timing.h"

#include <time.h>

bool timing_now(timestamp_t *timestamp) {
    struct timespec now;

    if (!timestamp) {
        return false;
    }

    if (clock_gettime(CLOCK_MONOTONIC, &now) != 0) {
        return false;
    }

    timestamp->seconds = (int64_t) now.tv_sec;
    timestamp->nanoseconds = (int64_t) now.tv_nsec;
    return true;
}

double timing_elapsed_seconds(
    const timestamp_t *start,
    const timestamp_t *end
) {
    double seconds;
    double nanoseconds;

    if (!start || !end) {
        return 0.0;
    }

    seconds = (double) end->seconds - (double) start->seconds;
    nanoseconds = (double) end->nanoseconds - (double) start->nanoseconds;
    return seconds + nanoseconds / 1000000000.0;
}
