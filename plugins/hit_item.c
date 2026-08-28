/* token="hit_item" -> sha256 -> <sha256(hit_item)>.dll（编辑器状态 EState + editor_lib 实现） */
#include "plug_api.h"
#include "editor_lib.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    EState *e = (EState*)pop_ptr(B);
    int vi = (int)pop_u32(B);
    Vector2 w; *B->stk_off -= 8; memcpy(&w, B->stk + *B->stk_off, 8);
    push_u32(B, (u32)hit_item(B, e, vi, w));
    B->run_next();
}

