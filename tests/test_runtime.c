#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <signal.h>
#include <stdio.h>
#include <sys/wait.h>
#include <unistd.h>
#include "runtime.h"
#include "ipc.h"

int main(void) {
    int status;
    const ipc_config_t config = {2, 10};
    ipc_result_t result;
    pid_t unrelated = fork();
    assert(unrelated >= 0);
    if (unrelated == 0) {
        _exit(23);
    }
    assert(runtime_configure(2000));
    assert(ipc_run_pipe(&config, &result));
    assert(result.validation.pass);
    assert(waitpid(unrelated, &status, 0) == unrelated);
    assert(WIFEXITED(status) && WEXITSTATUS(status) == 23);
    assert(!runtime_configure(0));
    assert(!runtime_configure(120001));
    assert(runtime_begin(1));
    runtime_cancel();
    assert(runtime_cancelled());
    assert(!runtime_ready(-1, 1));
    assert(runtime_begin(1));
    assert(!runtime_cancelled());
    puts("test_runtime: PASS");
    return 0;
}
