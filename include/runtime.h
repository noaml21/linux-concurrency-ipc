#ifndef RUNTIME_H
#define RUNTIME_H

#include <stdbool.h>
#include <stdint.h>
#include <sys/types.h>
#include <sys/sem.h>

/* One experiment at a time per process. Configure before starting workers. */
bool runtime_configure(uint32_t deadline_ms);
bool runtime_begin(uint32_t workers);
bool runtime_cancelled(void);
void runtime_cancel(void);
const char *runtime_reason(void);
pid_t runtime_fork(void);
pid_t runtime_wait(int *status, int options);
int runtime_semop(int id, struct sembuf *actions, size_t count);
bool runtime_ready(int fd, short events);
void runtime_child_fault(void);
void runtime_consumer_delay(void);

#endif
