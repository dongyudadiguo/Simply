/* token="drag_out" -> sha256 -> <sha256(drag_out)>.dll（编辑器状态 EState + editor_lib 实现） */
#include "plug_api.h"
#include "editor_lib.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    EState *e = (EState*)pop_ptr(B);
    int vi = (int)pop_u32(B);
    int i = (int)pop_u32(B);
    drag_out(B, e, vi, i);
    B->run_next();
}

