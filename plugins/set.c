#include "simply.h"
#include <stdlib.h>
#include <string.h>

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    const uint8_t *pay; u32 plen; B->cur_payload(&pay, &plen);
    uint32_t numsize; memcpy(&numsize, B->num + *B->num_off - 4, 4);   /* 结果大小（刚写入） */
    uint32_t v = *B->var_off;
    memcpy(B->var + v, pay, plen); v += plen;                  /* name */
    memcpy(B->var + v, &plen, 4); v += 4;                          /* nsize */
    uint64_t vptr = *B->stk_off - numsize; memcpy(B->var + v, &vptr, 8); v += 8;  /* vptr */
    memcpy(B->var + v, &numsize, 4); v += 4;                       /* vsize */
    *B->var_off = v;
    *B->stk_off += numsize;                                         /* 值已登记，栈推进 */
    *B->num_off += 4;
    B->run_next();
}
