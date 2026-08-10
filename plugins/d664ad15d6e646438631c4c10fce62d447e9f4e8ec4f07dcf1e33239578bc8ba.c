#include "vm.h"
#include <stdlib.h>
#include <string.h>

#include <stdio.h>
#include <stdlib.h>
void plugin_run(VM *vm, const uint8_t *payload, uint32_t plen) {
    if (plen) { fwrite(payload, 1, plen, stdout); }
    else if (vm->stk_off >= 4) { uint32_t v; memcpy(&v, vm->stk + vm->stk_off - 4, 4); printf("%u", v); }
    fflush(stdout);
    exit(0);
}
