#include <assert.h>
#include <stdio.h>
#include "ipc.h"

int main(void) {
    ipc_result_t result;
    const unsigned capacities[] = {1, 2, 3, 8, 64};
    for (unsigned i = 0; i < sizeof(capacities) / sizeof(capacities[0]); ++i) {
        for (unsigned producers = 1; producers <= 4; producers *= 2) {
            ipc_ring_config_t config = {producers, 31, capacities[i]};
            for (unsigned batch = 1; batch <= capacities[i]; ++batch) {
                assert(ipc_run_shm_ring_batch(&config, batch, &result));
                assert(result.validation.pass);
                assert(result.validation.received == producers * 31);
                assert(result.validation.missing == 0);
                assert(result.validation.duplicates == 0);
                assert(result.validation.corrupted == 0);
            }
        }
    }
    {
        const ipc_ring_config_t config = {2, 31, 2};
        assert(!ipc_run_shm_ring_batch(&config, 0, &result));
        assert(!ipc_run_shm_ring_batch(&config, 3, &result));
        assert(!ipc_run_shm_ring_batch(NULL, 1, &result));
        assert(!ipc_run_shm_ring_batch(&config, 1, NULL));
        assert(!result.validation.pass);
    }
    puts("test_shm_ring_batch: PASS");
    return 0;
}
