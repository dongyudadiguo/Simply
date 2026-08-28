/* token="frame_combo" -> sha256 -> <sha256(frame_combo)>.dll（编辑器状态 EState + editor_lib 实现） */
#include "plug_api.h"
#include "editor_lib.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    EState *e = (EState*)pop_ptr(B);
    int altl = IsKeyDown(KEY_LEFT_ALT), altr = IsKeyDown(KEY_RIGHT_ALT);
    int ctrl = IsKeyDown(KEY_LEFT_CONTROL) || IsKeyDown(KEY_RIGHT_CONTROL);
    int shift = IsKeyDown(KEY_LEFT_SHIFT) || IsKeyDown(KEY_RIGHT_SHIFT);
    if (IsKeyPressed(KEY_LEFT_ALT)) e->pressed_combo |= 1;
    if (IsKeyPressed(KEY_RIGHT_ALT)) e->pressed_combo |= 2;
    if (IsKeyPressed(KEY_LEFT_CONTROL) || IsKeyPressed(KEY_RIGHT_CONTROL)) e->pressed_combo |= 4;
    if (IsKeyPressed(KEY_LEFT_SHIFT) || IsKeyPressed(KEY_RIGHT_SHIFT)) e->pressed_combo |= 8;
    if (!altl && !altr && !ctrl && !shift) {
        if (e->pressed_combo) {
            if (e->edit_i < 0) combo_insert(B, e, e->pressed_combo);
            e->pressed_combo = 0;
        }
    }
    if (IsKeyPressed(KEY_LEFT_SHIFT) || IsKeyPressed(KEY_RIGHT_SHIFT)) { if (!ctrl) e->sel_start = pointer_pos(B, e); }
    if ((!shift) && e->sel_start >= 0) { sel_copy(B, e); e->sel_start = -1; }
    if (IsKeyPressed(KEY_DELETE)) e->del_start = pointer_pos(B, e);
    if (IsKeyReleased(KEY_DELETE) && e->del_start >= 0) { sel_del(B, e); e->del_start = -1; }
    if (IsKeyPressed(KEY_INSERT)) paste(B, e);
    e->prev_altl = altl; e->prev_altr = altr; e->prev_ctrl = ctrl; e->prev_shift = shift;
    B->run_next();
}

