/* token="frame_space" -> sha256 -> <sha256(frame_space)>.dll（编辑器状态 EState + editor_lib 实现） */
#include "plug_api.h"
#include "editor_lib.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    EState *e = (EState*)pop_ptr(B);
    if (IsKeyDown(KEY_SPACE) && !e->prev_space) space_insert(B, e);
    e->prev_space = IsKeyDown(KEY_SPACE);
    if (IsKeyPressed(KEY_ENTER) && e->input_len > 0) {
        if (!e->cand_ready) build_cands(B, e);
        for (int i = 0; i < e->cand_n; i++)
            if (strncmp(e->cands[i], e->input_str, e->input_len) == 0) { strcpy(e->input_str, e->cands[i]); e->input_len = (u32)strlen(e->input_str); break; }
    }
    if (e->edit_i >= 0 && IsKeyPressed(KEY_ENTER)) e->edit_i = -1;
    B->run_next();
}

