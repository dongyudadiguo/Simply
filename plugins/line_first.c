/* token="line_first" -> sha256 -> <sha256(line_first)>.dll（编辑器状态 EState + editor_lib 实现） */
#include "plug_api.h"
#include "editor_lib.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    EState *e = (EState*)pop_ptr(B);
    int j = (int)pop_u32(B);
    push_u32(B, (u32)line_first(e, j));
    B->run_next();
}

