#define _GNU_SOURCE
#include "runtime.h"

#include <errno.h>
#include <poll.h>
#include <signal.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

_Static_assert(ATOMIC_INT_LOCK_FREE == 2, "signal cancellation requires lock-free int");
static atomic_int stopped;
static uint32_t deadline_ms = 30000;
static double deadline;
static pid_t children[64];
static size_t child_count;
static double shutdown_started;

static double now(void) {
    struct timespec time;
    if (clock_gettime(CLOCK_MONOTONIC, &time) != 0) {
        atomic_store(&stopped, 1);
        return 0;
    }
    return (double) time.tv_sec + (double) time.tv_nsec / 1e9;
}

static void interrupt_run(int signal_number) {
    (void) signal_number;
    atomic_store(&stopped, 1);
}

bool runtime_configure(uint32_t milliseconds) {
    struct sigaction action = {0};
    if (milliseconds == 0 || milliseconds > 120000) {
        return false;
    }
    deadline_ms = milliseconds;
    action.sa_handler = interrupt_run;
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGINT, &action, NULL) || sigaction(SIGTERM, &action, NULL)) {
        return false;
    }
    action.sa_handler = SIG_IGN;
    return sigaction(SIGPIPE, &action, NULL) == 0;
}

bool runtime_begin(uint32_t workers) {
    if (workers == 0 || workers > 64) {
        return false;
    }
    for (size_t i = 0; i < child_count; ++i) {
        if (children[i] > 0) {
            return false;
        }
    }
    child_count = 0;
    shutdown_started = 0;
    atomic_store(&stopped, 0);
    deadline = now() + (double) deadline_ms / 1000;
    return true;
}

bool runtime_cancelled(void) {
    if (atomic_load(&stopped)) {
        return true;
    }
    if (deadline > 0 && now() >= deadline) {
        atomic_store(&stopped, 2);
        return true;
    }
    return false;
}

void runtime_cancel(void) {
    atomic_store(&stopped, 1);
}

const char *runtime_reason(void) {
    return atomic_load(&stopped) == 2 ? "deadline exceeded" : "cancelled or worker failed";
}

#ifdef IPC_TESTING
static bool fault(const char *name) {
    const char *value = getenv("IPC_LAB_TEST_FAULT");
    return value && strcmp(value, name) == 0;
}
#endif

pid_t runtime_fork(void) {
    pid_t parent = getpid();
    pid_t child;
    if (runtime_cancelled() || child_count == 64) {
        errno = ECANCELED;
        return -1;
    }
#ifdef IPC_TESTING
    if (child_count == 1 && fault("startup")) {
        runtime_cancel();
        errno = EAGAIN;
        return -1;
    }
#endif
    child = fork();
    if (child == 0) {
        /* Linux closes inherited anonymous resources if the owner dies. */
        if (prctl(PR_SET_PDEATHSIG, SIGKILL) != 0 || getppid() != parent) {
            _exit(1);
        }
    } else if (child > 0) {
        children[child_count++] = child;
#ifdef IPC_TESTING
        fprintf(stderr, "owned_pid=%ld\n", (long) child);
#endif
    } else {
        runtime_cancel();
    }
    return child;
}

static void escalate(void) {
    double current = now();
    int signal_number;
    if (shutdown_started == 0) {
        shutdown_started = current;
    }
    signal_number = current - shutdown_started < 0.2 ? SIGTERM : SIGKILL;
    for (size_t i = 0; i < child_count; ++i) {
        if (children[i] > 0) {
            /* Unreaped children retain their PID: no PID reuse signal race. */
            kill(children[i], signal_number);
        }
    }
}

pid_t runtime_wait(int *status, int options) {
    for (;;) {
        bool pending = false;
        for (size_t i = 0; i < child_count; ++i) {
            pid_t waited;
            if (children[i] <= 0) {
                continue;
            }
            pending = true;
            waited = waitpid(children[i], status, WNOHANG);
            if (waited > 0) {
                children[i] = 0;
                if (!WIFEXITED(*status) || WEXITSTATUS(*status) != 0) {
                    runtime_cancel();
                }
                return waited;
            }
            if (waited < 0 && errno != EINTR) {
                children[i] = 0;
                runtime_cancel();
                return -1;
            }
        }
        if (!pending) {
            errno = ECHILD;
            return -1;
        }
        if (runtime_cancelled()) {
            escalate();
        }
        if (options & WNOHANG) {
            return 0;
        }
        {
            const struct timespec pause = {0, 1000000};
            nanosleep(&pause, NULL);
        }
    }
}

int runtime_semop(int id, struct sembuf *actions, size_t count) {
    while (!runtime_cancelled()) {
        const struct timespec timeout = {0, 50000000};
        int result = semtimedop(id, actions, count, &timeout);
        if (result == 0 || (errno != EINTR && errno != EAGAIN)) {
            return result;
        }
    }
    errno = ECANCELED;
    return -1;
}

bool runtime_ready(int fd, short events) {
    struct pollfd descriptor = {fd, events, 0};
    while (!runtime_cancelled()) {
        int result = poll(&descriptor, 1, 50);
        if (result > 0) {
            return true; /* read/write reports EOF, EPIPE, or invalid descriptor. */
        }
        if (result < 0 && errno != EINTR) {
            return false;
        }
    }
    errno = ECANCELED;
    return false;
}

void runtime_child_fault(void) {
#ifdef IPC_TESTING
    static bool injected;
    if (!injected) {
        injected = true;
        if (fault("producer-fail")) {
            _exit(70);
        }
        if (fault("producer-stall")) {
            raise(SIGSTOP); /* Requires owner escalation; holds reservation/lock. */
        }
        if (fault("cancel")) {
            kill(getppid(), SIGTERM);
        }
    }
#endif
}

void runtime_consumer_delay(void) {
#ifdef IPC_TESTING
    if (fault("slow-consumer")) {
        const struct timespec pause = {0, 2000000};
        nanosleep(&pause, NULL);
    }
#endif
}
