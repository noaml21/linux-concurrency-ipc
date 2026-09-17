#include "sync.h"

#include <pthread.h>
#include <stdint.h>
#include <stdlib.h>

#include "timing.h"
#include "runtime.h"

typedef struct {
    uint64_t *counter;
    pthread_mutex_t *mutex;
    uint64_t operations;
    bool failed;
} worker_context_t;

static bool allocation_size_is_valid(size_t count, size_t element_size) {
    return count <= SIZE_MAX / element_size;
}

static void *increment_counter(void *argument) {
    worker_context_t *context = argument;

    for (uint64_t operation = 0;
         operation < context->operations;
         ++operation) {
        uint64_t value;

        if (runtime_cancelled()) {
            context->failed = true;
            break;
        }

        if (pthread_mutex_lock(context->mutex) != 0) {
            context->failed = true;
            break;
        }

        value = *context->counter;
        *context->counter = value + 1;

        if (pthread_mutex_unlock(context->mutex) != 0) {
            context->failed = true;
            break;
        }
    }

    return NULL;
}

bool sync_run_threads_mutex(
    const sync_config_t *config,
    sync_result_t *result
) {
    pthread_t *threads;
    worker_context_t *contexts;
    pthread_mutex_t mutex;
    timestamp_t start;
    timestamp_t end;
    uint64_t counter = 0;
    uint64_t expected;
    uint32_t threads_created = 0;
    bool succeeded = true;

    if (!result) {
        return false;
    }

    *result = (sync_result_t) {0};

    if (!config) {
        return false;
    }

    if (config->workers == 0 || config->operations_per_worker == 0) {
        return false;
    }

    if (config->operations_per_worker > UINT64_MAX / config->workers) {
        return false;
    }
    if (!runtime_begin(config->workers)) {
        return false;
    }

    expected = (uint64_t) config->workers * config->operations_per_worker;

    if (!allocation_size_is_valid(config->workers, sizeof(*threads)) ||
        !allocation_size_is_valid(config->workers, sizeof(*contexts))) {
        return false;
    }

    threads = calloc((size_t) config->workers, sizeof(*threads));
    contexts = calloc((size_t) config->workers, sizeof(*contexts));
    if (!threads || !contexts) {
        free(contexts);
        free(threads);
        return false;
    }

    if (pthread_mutex_init(&mutex, NULL) != 0) {
        free(contexts);
        free(threads);
        return false;
    }

    if (!timing_now(&start)) {
        succeeded = false;
    }

    if (succeeded) {
        for (uint32_t worker = 0; worker < config->workers; ++worker) {
            contexts[worker].counter = &counter;
            contexts[worker].mutex = &mutex;
            contexts[worker].operations = config->operations_per_worker;

            if (pthread_create(
                    &threads[worker],
                    NULL,
                    increment_counter,
                    &contexts[worker]
                ) != 0) {
                runtime_cancel();
                succeeded = false;
                break;
            }

            ++threads_created;
        }
    }

    for (uint32_t worker = 0; worker < threads_created; ++worker) {
        if (pthread_join(threads[worker], NULL) != 0) {
            succeeded = false;
        } else if (contexts[worker].failed) {
            succeeded = false;
        }
    }

    if (succeeded && !timing_now(&end)) {
        succeeded = false;
    }

    if (succeeded && counter != expected) {
        succeeded = false;
    }

    if (succeeded) {
        result->expected = expected;
        result->observed = counter;
        result->elapsed_seconds = timing_elapsed_seconds(&start, &end);
        if (result->elapsed_seconds > 0.0) {
            result->operations_per_second =
                (double) expected / result->elapsed_seconds;
        }
    }

    if (pthread_mutex_destroy(&mutex) != 0) {
        succeeded = false;
    }

    free(contexts);
    free(threads);
    return succeeded && !runtime_cancelled();
}
