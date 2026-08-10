#include "../vm.h"
#include <stdlib.h>
#include <string.h>

void plugin_run(VM *vm, const uint8_t *payload, uint32_t plen) {
    (void)payload; (void)plen;
    vm->cb_reset(vm);
}
