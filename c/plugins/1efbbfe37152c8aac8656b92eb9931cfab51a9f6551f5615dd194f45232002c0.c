#include "../vm.h"
#include <stdlib.h>
#include <string.h>

void plugin_run(VM *vm, const uint8_t *payload, uint32_t plen) {
    if (plen >= 8) {
        uint8_t b1, b2;
        vm->cb_hand_get(vm, payload, &b1, &b2);
        if (b1) { vm->cb_hand_set(vm, payload, 0, b2); vm->cb_run_block(vm, payload + 8, plen - 8); }
        else if (b2) { vm->cb_run_block(vm, payload + 8, plen - 8); }
        else vm->cb_run_next(vm);
    } else vm->cb_run_next(vm);
}
