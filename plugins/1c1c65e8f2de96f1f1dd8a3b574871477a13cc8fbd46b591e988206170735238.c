#include "vm.h"
#include <stdlib.h>
#include <string.h>

#include <stdio.h>
void plugin_run(VM *vm, const uint8_t *payload, uint32_t plen) {
    int lo = 1, hi = 100;
    if (plen) { char buf[64]; uint32_t n = plen < 63 ? plen : 63;
        memcpy(buf, payload, n); buf[n] = 0;
        int a = 0, b = 0; int cnt = sscanf(buf, "%d %d", &a, &b);
        if (cnt > 0) lo = a; if (cnt > 1) hi = b;
    }
    uint32_t v = (uint32_t)(lo + (hi > lo ? rand() % (hi - lo + 1) : 0));
    vm->cb_push(vm, (uint8_t*)&v, 4);
    vm->cb_write_num(vm, 4);
    vm->cb_run_next(vm);
}
