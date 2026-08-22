#include "io.h"

#include <errno.h>
#include <stdint.h>
#include <unistd.h>

bool write_all(int fd, const void *buffer, size_t size) {
    const unsigned char *current = buffer;
    size_t remaining = size;

    if (!buffer && size > 0) {
        return false;
    }

    while (remaining > 0) {
        ssize_t written = write(fd, current, remaining);

        if (written < 0) {
            if (errno == EINTR) {
                continue;
            }
            return false;
        }

        if (written == 0) {
            return false;
        }

        current += (size_t) written;
        remaining -= (size_t) written;
    }

    return true;
}

bool read_full(int fd, void *buffer, size_t size) {
    unsigned char *current = buffer;
    size_t remaining = size;

    if (!buffer && size > 0) {
        return false;
    }

    while (remaining > 0) {
        ssize_t bytes_read = read(fd, current, remaining);

        if (bytes_read < 0) {
            if (errno == EINTR) {
                continue;
            }
            return false;
        }

        if (bytes_read == 0) {
            return false;
        }

        current += (size_t) bytes_read;
        remaining -= (size_t) bytes_read;
    }

    return true;
}

io_read_result_t read_full_or_eof(
    int fd,
    void *buffer,
    size_t size
) {
    unsigned char *current = buffer;
    size_t remaining = size;

    if (!buffer && size > 0) {
        return IO_READ_ERROR;
    }

    while (remaining > 0) {
        ssize_t bytes_read = read(fd, current, remaining);

        if (bytes_read < 0) {
            if (errno == EINTR) {
                continue;
            }
            return IO_READ_ERROR;
        }

        if (bytes_read == 0) {
            if (remaining == size) {
                return IO_READ_EOF;
            }
            return IO_READ_ERROR;
        }

        current += (size_t) bytes_read;
        remaining -= (size_t) bytes_read;
    }

    return IO_READ_FULL;
}
