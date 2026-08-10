#include "../vm.h"
#include <stdlib.h>
#include <string.h>

void plugin_run(VM *vm, const uint8_t *payload, uint32_t plen) {
    uint32_t numsize; memcpy(&numsize, vm->num + vm->num_off - 4, 4);  /* 结果大小（刚写入） */
    uint32_t v = vm->var_off;
    memcpy(vm->var + v, payload, plen); v += plen;                      /* name */
    memcpy(vm->var + v, &plen, 4); v += 4;                              /* nsize */
    uint64_t vptr = vm->stk_off - numsize; memcpy(vm->var + v, &vptr, 8); v += 8;  /* vptr */
    memcpy(vm->var + v, &numsize, 4); v += 4;                           /* vsize */
    vm->var_off = v;
    vm->stk_off += numsize;                                             /* 值已登记，栈推进 */
    vm->num_off += 4;
    vm->cb_run_next(vm);
}
