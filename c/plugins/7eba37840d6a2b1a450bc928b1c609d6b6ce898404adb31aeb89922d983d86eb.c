#include "../vm.h"
#include <stdlib.h>
#include <string.h>

#include <stdio.h>
void plugin_run(VM *vm, const uint8_t *payload, uint32_t plen) {
    uint32_t v = (uint32_t)strtoul((const char*)payload, NULL, 10);
    vm->cb_push(vm, (uint8_t*)&v, 4);
    vm->cb_write_num(vm, 4);
    vm->cb_run_next(vm);
}
