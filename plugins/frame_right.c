/* token="frame_right" -> sha256 -> <sha256(frame_right)>.dll（编辑器状态 EState + editor_lib 实现） */
#include "plug_api.h"
#include "editor_lib.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    EState *e = (EState*)pop_ptr(B);
    if (IsMouseButtonDown(MOUSE_BUTTON_RIGHT) && !e->prev_rb) {
        int closed = 0;
        for (int i = 1; i < e->view_n; i++) {
            if (CheckCollisionPointRec(e->mouse_world, (Rectangle){e->views[i].pos.x, e->views[i].pos.y, 200, RH})) {
                e->views[i].klen = 0; closed = 1;
                compact_views(e);
                e->cur_v = 0; e->edit_i = -1; e->edit_v = 0;
                break;
            }
        }
        if (!closed) {
            int si = hit_view(e, e->mouse_world);
            if (si >= 0) {
                int i = hit_item(B, e, si, e->mouse_world);
                if (i >= 0) drag_out(B, e, si, i);
            }
        }
    }
    e->prev_rb = IsMouseButtonDown(MOUSE_BUTTON_RIGHT);
    B->run_next();
}

