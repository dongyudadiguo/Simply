/* token="frame_left" -> sha256 -> <sha256(frame_left)>.dll（编辑器状态 EState + editor_lib 实现） */
#include "plug_api.h"
#include "editor_lib.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    EState *e = (EState*)pop_ptr(B);
    if (IsMouseButtonPressed(MOUSE_BUTTON_LEFT)) {
        e->ldrag = -1;
        int si = hit_view(e, e->mouse_world);
        if (si >= 0) {
            int i = hit_item(B, e, si, e->mouse_world);
            if (i >= 0) {
                size_t n; Toks f; Tok *ts = view_toks(B, e, si, &n, &f);
                if (name_is(&ts[i], "handrun")) {
                    float ox, oy, ow;
                    if (find_item_rect(B, e, si, i, &ox, &oy, &ow)) {
                        int relx = (int)(e->mouse_world.x - (ox + ow - 22));
                        uint8_t b1, b2; B->hand_get(ts[i].payload, &b1, &b2);
                        if (relx >= 0 && relx < 10) B->hand_set(ts[i].payload, b1 ? 0 : 1, b2);
                        else if (relx >= 12 && relx < 24) B->hand_set(ts[i].payload, b1, b2 ? 0 : 1);
                    }
                }
                free_fetched(&f);
            } else { e->ldrag = si; e->ldrag_off = Vector2Subtract(e->mouse_world, e->views[si].pos); }
        }
    }
    if (IsMouseButtonDown(MOUSE_BUTTON_LEFT) && e->ldrag >= 0) e->views[e->ldrag].pos = Vector2Subtract(e->mouse_world, e->ldrag_off);
    if (IsMouseButtonReleased(MOUSE_BUTTON_LEFT)) e->ldrag = -1;
    B->run_next();
}

