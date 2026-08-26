/* token="st" -> sha256 -> <sha256(st)>.dll（plug_api.h 结构） */
#include "plug_api.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    u32 n = pop_u32(B);
    uint8_t *dst = (uint8_t*)pop_ptr(B);
    const uint8_t *data = B->stk + *B->stk_off - n;   /* 栈顶 n 字节为数据 */
    memcpy(dst, data, n);
    *B->stk_off -= n;                            /* 弹出数据 */
    B->run_next();
}

