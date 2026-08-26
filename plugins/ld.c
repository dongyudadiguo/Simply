/* token="ld" -> sha256 -> <sha256(ld)>.dll（plug_api.h 结构） */
#include "plug_api.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    u32 n = pop_u32(B);
    const uint8_t *p = (const uint8_t*)pop_ptr(B);
    push_bytes(B, p, n);                         /* 从指针读 n 字节压栈 */
    B->run_next();
}

