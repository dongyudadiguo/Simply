#include "../vm.h"
#include <stdlib.h>
#include <string.h>

void plugin_run(VM *vm, const uint8_t *payload, uint32_t plen) {
    uint32_t v = vm->var_off;
    while (v > 0) {
        uint32_t nsize, vsize; uint64_t vptr;
        memcpy(&nsize, vm->var + v - 16, 4);
        memcpy(&vptr, vm->var + v - 12, 8);
        memcpy(&vsize, vm->var + v - 4, 4);
        if (nsize == plen && memcmp(vm->var + v - 16 - nsize, payload, plen) == 0) {
            vm->cb_push(vm, vm->stk + (size_t)vptr, vsize);
            break;
        }
        v -= 16 + nsize;
    }
    vm->cb_run_next(vm);
}
