/* token="hit_view" -> sha256 -> <sha256(hit_view)>.dll（编辑器状态 EState + editor_lib 实现） */
#include "plug_api.h"
#include "editor_lib.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    EState *e = (EState*)pop_ptr(B);
    Vector2 w; *B->stk_off -= 8; memcpy(&w, B->stk + *B->stk_off, 8);
    push_u32(B, (u32)hit_view(e, w));
    B->run_next();
}

