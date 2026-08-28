/* token="find_item_rect" -> sha256 -> <sha256(find_item_rect)>.dll（编辑器状态 EState + editor_lib 实现） */
#include "plug_api.h"
#include "editor_lib.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    EState *e = (EState*)pop_ptr(B);
    int vi = (int)pop_u32(B);
    int idx = (int)pop_u32(B);
    int found = find_item_rect(B, e, vi, idx, &e->tmp_ox, &e->tmp_oy, &e->tmp_ow);
    push_u32(B, (u32)found);
    B->run_next();
}

