/* token="update_edit" -> sha256 -> <sha256(update_edit)>.dll（编辑器状态 EState + editor_lib 实现） */
#include "plug_api.h"
#include "editor_lib.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    EState *e = (EState*)pop_ptr(B);
    update_edit(B, e);
    B->run_next();
}

