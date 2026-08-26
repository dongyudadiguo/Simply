/* token="sel_del" -> sha256 -> <sha256(sel_del)>.dll（编辑器状态 EState + editor_lib 实现） */
#include "plug_api.h"
#include "editor_lib.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    EState *e = (EState*)pop_ptr(B);
    sel_del(B, e);
    B->run_next();
}

