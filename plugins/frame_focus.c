/* token="frame_focus" -> sha256 -> <sha256(frame_focus)>.dll（编辑器状态 EState + editor_lib 实现） */
#include "plug_api.h"
#include "editor_lib.h"

extern void *__stdcall GetFocus(void);
extern void *__stdcall SetFocus(void *hwnd);
__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    EState *e = (EState*)pop_ptr(B);
    (void)e;
    Vector2 mp = GetMousePosition();
    if (mp.x >= 0 && mp.y >= 0 && mp.x < GetScreenWidth() && mp.y < GetScreenHeight()) {
        void *wh = GetWindowHandle();
        if (GetFocus() != wh) SetFocus(wh);
    }
    B->run_next();
}

