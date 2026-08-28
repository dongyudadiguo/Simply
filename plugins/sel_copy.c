/* token="sel_copy" -> sha256 -> <sha256(sel_copy)>.dll（编辑器状态 EState + editor_lib 实现） */
#include "plug_api.h"
#include "editor_lib.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    EState *e = (EState*)pop_ptr(B);
    sel_copy(B, e);
    B->run_next();
}

