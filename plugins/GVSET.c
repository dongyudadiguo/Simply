/* token="GVSET" -> sha256 -> <sha256(GVSET)>.dll（plug_api.h 结构） */
#include "plug_api.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    const uint8_t *pay; u32 plen; B->cur_payload(&pay, &plen);
    u32 n = pop_u32(B);
    const uint8_t *data = B->stk + *B->stk_off - n;
    B->gv_set(pay, plen, data, n);               /* 拷贝存储 */
    *B->stk_off -= n;
    B->run_next();
}

