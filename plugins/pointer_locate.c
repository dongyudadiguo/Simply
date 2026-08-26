/* token="pointer_locate" -> sha256 -> <sha256(pointer_locate)>.dll（编辑器状态 EState + editor_lib 实现） */
#include "plug_api.h"
#include "editor_lib.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    EState *e = (EState*)pop_ptr(B);
    int pos = pointer_locate(B, e, &e->tmp_ox, &e->tmp_oy);
    push_u32(B, (u32)pos);
    B->run_next();
}

