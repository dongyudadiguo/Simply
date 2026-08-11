// editor.c —— 图形编辑器插件（raylib，内建编译进 vm）
#include "simply.h"
#include "raylib.h"
#include <string.h>
#include <stdlib.h>

static int first = 1;

__declspec(dllexport) void run(void) {
    /* 当前块 key 从返回栈顶读（写进 retpoint 的合成 token） */
    const uint8_t *ck; uint32_t ckl;
    cur_key_of(&ck, &ckl);
    if (first) {
        first = 0;
        SetTraceLogLevel(LOG_NONE);
        InitWindow(900, 640, "Simply Editor (C/raylib)");
        SetTargetFPS(60);
        /* 当前块 toks 载入内存（editor 拥有，动态读取会响应） */
        size_t n = 0;
        if (!cur_get(ck, ckl, &n)) {
            Toks ts = load_toks(ck, ckl);
            cur_set(ck, ckl, ts.tok, ts.n);
        }
    }
    /* 每帧渲染 */
    BeginDrawing();
    ClearBackground(RAYWHITE);
    DrawText("ESC = 退出", 20, 16, 16, GRAY);
    char cur[96]; uint32_t cl = ckl < 90 ? ckl : 90;
    memcpy(cur, ck ? ck : (const uint8_t*)"(boot)", ck ? cl : 6);
    cur[ck ? cl : 6] = 0;
    DrawText(cur, 20, 40, 16, DARKGRAY);
    size_t n = 0;
    Tok *toks = cur_get(ck, ckl, &n);
    int y = 70;
    for (size_t i = 0; i < n; i++) {
        char nm[64]; uint32_t ln = toks[i].nlen < 63 ? toks[i].nlen : 63;
        memcpy(nm, toks[i].name, ln); nm[ln] = 0;
        DrawRectangle(20, y, 200, 24, LIGHTGRAY);
        DrawText(nm, 28, y + 3, 16, BLACK);
        y += 30;
    }
    EndDrawing();
    if (WindowShouldClose()) exit(0);

    reset();                          /* editor 接棒 = rerun：重跑当前块（零大小 data = editor） */
}
