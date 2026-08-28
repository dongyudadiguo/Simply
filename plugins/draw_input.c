/* token="draw_input" -> sha256 -> <sha256(draw_input)>.dll（编辑器状态 EState + editor_lib 实现） */
#include "plug_api.h"
#include "editor_lib.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    EState *e = (EState*)pop_ptr(B);
    if (e->input_len > 0) {
        char tmp[400];
        sprintf(tmp, "%s%s", e->input_str, e->completion);
        DrawText(tmp, GetMouseX() + 20, GetMouseY(), 20, C_INP);
    }
    B->run_next();
}

