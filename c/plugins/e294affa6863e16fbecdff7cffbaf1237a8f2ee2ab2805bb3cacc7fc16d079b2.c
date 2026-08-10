#include "../vm.h"
#include <stdlib.h>
#include <string.h>

void plugin_run(VM *vm, const uint8_t *payload, uint32_t plen) {
    (void)payload; (void)plen;
    uint32_t o = vm->stk_off;
    uint32_t a, b; memcpy(&a, vm->stk + o - 8, 4); memcpy(&b, vm->stk + o - 4, 4);
    uint32_t r = a > b ? 1 : 0;
    memcpy(vm->stk + o - 8, &r, 4);
    vm->stk_off = o - 4;
    vm->cb_write_num(vm, 4);
    vm->cb_run_next(vm);
}
