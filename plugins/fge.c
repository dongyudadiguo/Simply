/* token="fge" -> sha256 -> <sha256(fge)>.dll（plug_api.h 结构） */
#include "plug_api.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    float b, a;
    *B->stk_off -= 4; memcpy(&b, B->stk + *B->stk_off, 4);
    *B->stk_off -= 4; memcpy(&a, B->stk + *B->stk_off, 4);
    u32 r = (a >= b) ? 1 : 0;
    push_u32(B, r);
    B->run_next();
}
