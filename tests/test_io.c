#include <assert.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include "io.h"

static void test_zero_size(void) {
    assert(write_all(-1, NULL, 0));
    assert(read_full(-1, NULL, 0));
}

static void test_normal_round_trip(void) {
    const unsigned char sent[] = {0x00, 0x11, 0x7f, 0x80, 0xfe, 0xff};
    unsigned char received[sizeof(sent)] = {0};
    int fds[2];

    assert(pipe(fds) == 0);
    assert(write_all(fds[1], sent, sizeof(sent)));
    assert(read_full(fds[0], received, sizeof(received)));
    assert(memcmp(sent, received, sizeof(sent)) == 0);

    close(fds[0]);
    close(fds[1]);
}

static void test_larger_round_trip(void) {
    unsigned char sent[4096];
    unsigned char received[sizeof(sent)];
    int fds[2];

    for (size_t i = 0; i < sizeof(sent); ++i) {
        sent[i] = (unsigned char) ((i * 37U + 11U) & 0xffU);
    }
    memset(received, 0, sizeof(received));

    assert(pipe(fds) == 0);
    assert(write_all(fds[1], sent, sizeof(sent)));
    assert(read_full(fds[0], received, sizeof(received)));
    assert(memcmp(sent, received, sizeof(sent)) == 0);

    close(fds[0]);
    close(fds[1]);
}

static void test_early_eof(void) {
    const unsigned char partial[] = {1, 2, 3};
    unsigned char received[6] = {0};
    int fds[2];

    assert(pipe(fds) == 0);
    assert(write_all(fds[1], partial, sizeof(partial)));
    close(fds[1]);

    assert(!read_full(fds[0], received, sizeof(received)));
    close(fds[0]);
}

static void test_invalid_buffer(void) {
    int fds[2];

    assert(pipe(fds) == 0);
    assert(!write_all(fds[1], NULL, 1));
    assert(!read_full(fds[0], NULL, 1));

    close(fds[0]);
    close(fds[1]);
}

static void test_read_full_or_eof_full_object(void) {
    const unsigned char sent[] = {0x10, 0x20, 0x30, 0x40};
    unsigned char received[sizeof(sent)] = {0};
    int fds[2];

    assert(pipe(fds) == 0);
    assert(write_all(fds[1], sent, sizeof(sent)));
    assert(read_full_or_eof(fds[0], received, sizeof(received))
           == IO_READ_FULL);
    assert(memcmp(sent, received, sizeof(sent)) == 0);

    close(fds[0]);
    close(fds[1]);
}

static void test_read_full_or_eof_clean_eof(void) {
    unsigned char received[4] = {0};
    int fds[2];

    assert(pipe(fds) == 0);
    close(fds[1]);

    assert(read_full_or_eof(fds[0], received, sizeof(received))
           == IO_READ_EOF);
    close(fds[0]);
}

static void test_read_full_or_eof_partial_eof(void) {
    const unsigned char partial[] = {1, 2};
    unsigned char received[4] = {0};
    int fds[2];

    assert(pipe(fds) == 0);
    assert(write_all(fds[1], partial, sizeof(partial)));
    close(fds[1]);

    assert(read_full_or_eof(fds[0], received, sizeof(received))
           == IO_READ_ERROR);
    close(fds[0]);
}

static void test_read_full_or_eof_zero_size(void) {
    assert(read_full_or_eof(-1, NULL, 0) == IO_READ_FULL);
}

static void test_read_full_or_eof_invalid_buffer(void) {
    assert(read_full_or_eof(-1, NULL, 1) == IO_READ_ERROR);
}

int main(void) {
    test_zero_size();
    test_normal_round_trip();
    test_larger_round_trip();
    test_early_eof();
    test_invalid_buffer();
    test_read_full_or_eof_full_object();
    test_read_full_or_eof_clean_eof();
    test_read_full_or_eof_partial_eof();
    test_read_full_or_eof_zero_size();
    test_read_full_or_eof_invalid_buffer();

    printf("test_io: PASS\n");
    return 0;
}
