#include "../vm.h"
#include <stdlib.h>
#include <string.h>

#include <stdio.h>
void plugin_run(VM *vm, const uint8_t *payload, uint32_t plen) {
    (void)payload; (void)plen;
    int v; if (scanf("%d", &v) != 1) v = 0;
    uint32_t u = (uint32_t)v;
    vm->cb_push(vm, (uint8_t*)&u, 4);
    vm->cb_write_num(vm, 4);
    vm->cb_run_next(vm);
}
