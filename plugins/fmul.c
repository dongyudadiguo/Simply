/* token="fmul" -> sha256 -> <sha256(fmul)>.dll（plug_api.h 结构） */
#include "plug_api.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    float b, a;
    *B->stk_off -= 4; memcpy(&b, B->stk + *B->stk_off, 4);
    *B->stk_off -= 4; memcpy(&a, B->stk + *B->stk_off, 4);
    float r = a * b;
    push_bytes(B, &r, 4);
    B->run_next();
}

