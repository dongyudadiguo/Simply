/* token="edit_append" -> sha256 -> <sha256(edit_append)>.dll（编辑器状态 EState + editor_lib 实现） */
#include "plug_api.h"
#include "editor_lib.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    EState *e = (EState*)pop_ptr(B);
    int ch = (int)pop_u32(B);
    edit_append(B, e, ch);
    B->run_next();
}

