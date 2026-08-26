/* token="combo_insert" -> sha256 -> <sha256(combo_insert)>.dll（编辑器状态 EState + editor_lib 实现） */
#include "plug_api.h"
#include "editor_lib.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    EState *e = (EState*)pop_ptr(B);
    int combo = (int)pop_u32(B);
    combo_insert(B, e, combo);
    B->run_next();
}

