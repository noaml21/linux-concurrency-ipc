CC = gcc
CPPFLAGS = -Iinclude
CFLAGS = -std=c11 -Wall -Wextra -Werror -pedantic

TEST_BINS = \
	build/test_record \
	build/test_validator \
	build/test_io \
	build/test_timing \
	build/test_process_unsafe \
	build/test_threads_mutex \
	build/test_processes_sem \
	build/test_pipe \
	build/test_fifo \
	build/test_shm_mailbox \
	build/test_shm_ring

.PHONY: app release test clean

app: build/linux-concurrency-ipc

release: build/linux-concurrency-ipc-release

test: $(TEST_BINS)
	./build/test_record
	./build/test_validator
	./build/test_io
	./build/test_timing
	./build/test_process_unsafe
	./build/test_threads_mutex
	./build/test_processes_sem
	./build/test_pipe
	./build/test_fifo
	./build/test_shm_mailbox
	./build/test_shm_ring

build/test_record: src/common/record.c tests/test_record.c include/record.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) src/common/record.c tests/test_record.c -o $@

build/test_validator: src/common/record.c src/common/validator.c tests/test_validator.c include/record.h include/validator.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) src/common/record.c src/common/validator.c tests/test_validator.c -o $@

build/test_io: src/common/io.c tests/test_io.c include/io.h src/common/runtime.c include/runtime.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) src/common/io.c tests/test_io.c src/common/runtime.c -o $@

build/test_timing: src/common/timing.c tests/test_timing.c include/timing.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) src/common/timing.c tests/test_timing.c -o $@

build/test_process_unsafe: src/common/timing.c src/sync/process_unsafe.c tests/test_process_unsafe.c include/timing.h include/sync.h src/common/runtime.c include/runtime.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) src/common/timing.c src/sync/process_unsafe.c tests/test_process_unsafe.c src/common/runtime.c -o $@

build/test_threads_mutex: src/common/timing.c src/sync/threads_mutex.c tests/test_threads_mutex.c include/timing.h include/sync.h src/common/runtime.c include/runtime.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -pthread src/common/timing.c src/sync/threads_mutex.c tests/test_threads_mutex.c src/common/runtime.c -o $@

build/test_processes_sem: src/common/timing.c src/sync/processes_sem.c tests/test_processes_sem.c include/timing.h include/sync.h src/common/runtime.c include/runtime.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) src/common/timing.c src/sync/processes_sem.c tests/test_processes_sem.c src/common/runtime.c -o $@

build/test_pipe: src/common/record.c src/common/validator.c src/common/io.c src/common/timing.c src/ipc/pipe.c tests/test_pipe.c include/record.h include/validator.h include/io.h include/timing.h include/ipc.h src/common/runtime.c include/runtime.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) src/common/record.c src/common/validator.c src/common/io.c src/common/timing.c src/ipc/pipe.c tests/test_pipe.c src/common/runtime.c -o $@

build/test_fifo: src/common/record.c src/common/validator.c src/common/io.c src/common/timing.c src/ipc/fifo.c tests/test_fifo.c include/record.h include/validator.h include/io.h include/timing.h include/ipc.h src/common/runtime.c include/runtime.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) src/common/record.c src/common/validator.c src/common/io.c src/common/timing.c src/ipc/fifo.c tests/test_fifo.c src/common/runtime.c -o $@

build/test_shm_mailbox: src/common/record.c src/common/validator.c src/common/timing.c src/ipc/shm_mailbox.c tests/test_shm_mailbox.c include/record.h include/validator.h include/timing.h include/ipc.h src/common/runtime.c include/runtime.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) src/common/record.c src/common/validator.c src/common/timing.c src/ipc/shm_mailbox.c tests/test_shm_mailbox.c src/common/runtime.c -o $@

build/test_shm_ring: src/common/record.c src/common/validator.c src/common/timing.c src/ipc/shm_ring.c tests/test_shm_ring.c include/record.h include/validator.h include/timing.h include/ipc.h src/common/runtime.c include/runtime.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) src/common/record.c src/common/validator.c src/common/timing.c src/ipc/shm_ring.c tests/test_shm_ring.c src/common/runtime.c -o $@

build/linux-concurrency-ipc: src/main.c src/common/record.c src/common/validator.c src/common/io.c src/common/timing.c src/sync/process_unsafe.c src/sync/threads_mutex.c src/sync/processes_sem.c src/ipc/pipe.c src/ipc/fifo.c src/ipc/shm_mailbox.c src/ipc/shm_ring.c include/record.h include/validator.h include/io.h include/timing.h include/sync.h include/ipc.h src/common/runtime.c include/runtime.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -pthread src/main.c src/common/record.c src/common/validator.c src/common/io.c src/common/timing.c src/sync/process_unsafe.c src/sync/threads_mutex.c src/sync/processes_sem.c src/ipc/pipe.c src/ipc/fifo.c src/ipc/shm_mailbox.c src/ipc/shm_ring.c src/common/runtime.c -o $@
	python3 scripts/build_info.py $@ "$(CC)" "$(CPPFLAGS) $(CFLAGS) -pthread"

build/linux-concurrency-ipc-release: src/main.c src/common/record.c src/common/validator.c src/common/io.c src/common/timing.c src/sync/process_unsafe.c src/sync/threads_mutex.c src/sync/processes_sem.c src/ipc/pipe.c src/ipc/fifo.c src/ipc/shm_mailbox.c src/ipc/shm_ring.c include/record.h include/validator.h include/io.h include/timing.h include/sync.h include/ipc.h src/common/runtime.c include/runtime.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -O2 -pthread src/main.c src/common/record.c src/common/validator.c src/common/io.c src/common/timing.c src/sync/process_unsafe.c src/sync/threads_mutex.c src/sync/processes_sem.c src/ipc/pipe.c src/ipc/fifo.c src/ipc/shm_mailbox.c src/ipc/shm_ring.c src/common/runtime.c -o $@
	python3 scripts/build_info.py $@ "$(CC)" "$(CPPFLAGS) $(CFLAGS) -O2 -pthread"

build:
	mkdir -p build

clean:
	rm -rf build

# Fault hooks are absent from production builds.
build/linux-concurrency-ipc-fault: $(wildcard src/common/*.c src/ipc/*.c src/sync/*.c include/*.h) src/main.c | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -DIPC_TESTING -pthread src/main.c src/common/*.c src/ipc/*.c src/sync/*.c -o $@
	python3 scripts/build_info.py $@ "$(CC)" "$(CPPFLAGS) $(CFLAGS) -DIPC_TESTING -pthread"

fault-test: build/linux-concurrency-ipc-fault
	python3 -m unittest discover -s tests/reliability -v

build/test_runtime: tests/test_runtime.c src/common/runtime.c src/ipc/pipe.c src/common/io.c src/common/validator.c src/common/record.c src/common/timing.c include/runtime.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/test_runtime.c src/common/runtime.c src/ipc/pipe.c src/common/io.c src/common/validator.c src/common/record.c src/common/timing.c -o $@

test: runtime-test
runtime-test: build/test_runtime
	./build/test_runtime

build/test_shm_ring_batch: tests/test_shm_ring_batch.c src/ipc/shm_ring.c src/common/runtime.c src/common/validator.c src/common/record.c src/common/timing.c include/ipc.h include/runtime.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/test_shm_ring_batch.c src/ipc/shm_ring.c src/common/runtime.c src/common/validator.c src/common/record.c src/common/timing.c -o $@

test: batch-test
batch-test: build/test_shm_ring_batch
	./build/test_shm_ring_batch

.PHONY: runtime-test batch-test fault-test sanitizer-test
SAFE_TEST_BINS = $(filter-out build/test_process_unsafe,$(TEST_BINS)) build/test_runtime build/test_shm_ring_batch
sanitizer-test:
	$(MAKE) -B $(SAFE_TEST_BINS) CFLAGS='-std=c11 -Wall -Wextra -Werror -pedantic -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -fno-pie -no-pie'
	@set -e; for binary in $(SAFE_TEST_BINS); do ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 $$binary; done
