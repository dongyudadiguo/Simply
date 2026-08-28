/* token="view_toks" -> sha256 -> <sha256(view_toks)>.dll（编辑器状态 EState + editor_lib 实现） */
#include "plug_api.h"
#include "editor_lib.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    EState *e = (EState*)pop_ptr(B);
    int vi = (int)pop_u32(B);
    size_t n = 0;
    Tok *t = view_toks(B, e, vi, &n, &e->tmp_toks);
    push_ptr(B, t);
    push_u32(B, (u32)n);
    B->run_next();
}

