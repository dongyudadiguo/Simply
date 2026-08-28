/* token="build_lines" -> sha256 -> <sha256(build_lines)>.dll（编辑器状态 EState + editor_lib 实现） */
#include "plug_api.h"
#include "editor_lib.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    EState *e = (EState*)pop_ptr(B);
    size_t n = pop_u32(B);
    Tok *toks = (Tok*)pop_ptr(B);
    build_lines(e, toks, n);
    B->run_next();
}

