/* token="pointer_pos" -> sha256 -> <sha256(pointer_pos)>.dll（编辑器状态 EState + editor_lib 实现） */
#include "plug_api.h"
#include "editor_lib.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    EState *e = (EState*)pop_ptr(B);
    push_u32(B, (u32)pointer_pos(B, e));
    B->run_next();
}

