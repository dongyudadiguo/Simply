/* token="GV" -> sha256 -> <sha256(GV)>.dll（plug_api.h 结构） */
#include "plug_api.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    const uint8_t *pay; u32 plen; B->cur_payload(&pay, &plen);
    u32 n = 0;
    const uint8_t *p = B->gv_get(pay, plen, &n);
    push_ptr(B, p);                              /* 值指针（表内，缺 NULL） */
    push_u32(B, n);                              /* 值长度 */
    B->run_next();
}

