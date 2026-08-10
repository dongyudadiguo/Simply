#include "simply.h"
#include <stdlib.h>
#include <string.h>

#include <stdio.h>
void rand_run(void) {
    int lo = 1, hi = 100;
    if (plen) { char buf[64]; uint32_t n = plen < 63 ? plen : 63;
        memcpy(buf, payload, n); buf[n] = 0;
        int a = 0, b = 0; int cnt = sscanf(buf, "%d %d", &a, &b);
        if (cnt > 0) lo = a; if (cnt > 1) hi = b;
    }
    uint32_t v = (uint32_t)(lo + (hi > lo ? rand() % (hi - lo + 1) : 0));
    push((uint8_t*)&v, 4);
    write_num(4);
    run_next();
}
