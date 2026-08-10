#include "vm.h"
#include <stdlib.h>
#include <string.h>

void plugin_run(VM *vm, const uint8_t *payload, uint32_t plen) {
    if (vm->stk_off > 0 && vm->stk[0] != 0 && plen) vm->cb_run_block(vm, payload, plen);
    else vm->cb_run_next(vm);
}
