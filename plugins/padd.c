/* token="padd" -> sha256 -> <sha256(padd)>.dll（plug_api.h 结构） */
#include "plug_api.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    u32 off = pop_u32(B);
    uintptr_t p = pop_ptr(B);
    push_ptr(B, (void*)(p + off));               /* 指针 + 偏移 */
    B->run_next();
}

