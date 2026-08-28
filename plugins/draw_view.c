/* token="draw_view" -> sha256 -> <sha256(draw_view)>.dll（编辑器状态 EState + editor_lib 实现） */
#include "plug_api.h"
#include "editor_lib.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    EState *e = (EState*)pop_ptr(B);
    int vi = (int)pop_u32(B);
    draw_view(B, e, vi);
    B->run_next();
}

