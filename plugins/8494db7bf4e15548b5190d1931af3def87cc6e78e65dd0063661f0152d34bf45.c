#include "vm.h"
#include <stdlib.h>
#include <string.h>

void plugin_run(VM *vm, const uint8_t *payload, uint32_t plen) {
    (void)payload; (void)plen;
    if (vm->stk_off > 0 && vm->stk[0] != 0) vm->cb_reset(vm);
    else vm->cb_run_next(vm);
}
