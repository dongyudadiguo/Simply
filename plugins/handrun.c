#include "simply.h"
#include <stdlib.h>
#include <string.h>

void handrun_run(void) {
    if (plen >= 8) {
        uint8_t b1, b2;
        hand_get(payload, &b1, &b2);
        if (b1) {
            hand_set(payload, 0, b2);
            uint32_t n = plen - 8;
            run_block((KEY){&n, payload + 8});
        }
        else if (b2) {
            uint32_t n = plen - 8;
            run_block((KEY){&n, payload + 8});
        }
        else run_next();
    } else run_next();
}
