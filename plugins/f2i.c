/* token="f2i" -> sha256 -> <sha256(f2i)>.dll（plug_api.h 结构） */
#include "plug_api.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    float a; *B->stk_off -= 4; memcpy(&a, B->stk + *B->stk_off, 4);
    u32 r = (u32)(int)a;                         /* float → int → u32 */
    push_u32(B, r);
    B->run_next();
}

