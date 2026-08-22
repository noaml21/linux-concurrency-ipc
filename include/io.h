#ifndef IO_H
#define IO_H

#include <stdbool.h>
#include <stddef.h>

typedef enum {
    IO_READ_FULL,
    IO_READ_EOF,
    IO_READ_ERROR
} io_read_result_t;

bool write_all(int fd, const void *buffer, size_t size);

bool read_full(int fd, void *buffer, size_t size);

io_read_result_t read_full_or_eof(
    int fd,
    void *buffer,
    size_t size
);

#endif
