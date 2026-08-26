/* token="update_completion" -> sha256 -> <sha256(update_completion)>.dll（编辑器状态 EState + editor_lib 实现） */
#include "plug_api.h"
#include "editor_lib.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    EState *e = (EState*)pop_ptr(B);
    update_completion(B, e);
    B->run_next();
}

