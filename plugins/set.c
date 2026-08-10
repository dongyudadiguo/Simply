#include "simply.h"
#include <stdlib.h>
#include <string.h>

void set_run(const uint8_t *payload, uint32_t plen) {
    uint32_t numsize; memcpy(&numsize, num + num_off - 4, 4);   /* 结果大小（刚写入） */
    uint32_t v = var_off;
    memcpy(var + v, payload, plen); v += plen;                  /* name */
    memcpy(var + v, &plen, 4); v += 4;                          /* nsize */
    uint64_t vptr = stk_off - numsize; memcpy(var + v, &vptr, 8); v += 8;  /* vptr */
    memcpy(var + v, &numsize, 4); v += 4;                       /* vsize */
    var_off = v;
    stk_off += numsize;                                         /* 值已登记，栈推进 */
    num_off += 4;
    run_next();
}
