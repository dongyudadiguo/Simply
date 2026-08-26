/* token="i2f" -> sha256 -> <sha256(i2f)>.dll（plug_api.h 结构） */
#include "plug_api.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    u32 a = pop_u32(B);
    float r = (float)(int)a;                     /* u32 → int → float */
    push_bytes(B, &r, 4);
    B->run_next();
}

