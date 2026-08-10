// editor.c —— 图形编辑器插件（raylib，内建编译进 vm）
#include "simply.h"
#include "raylib.h"
#include <string.h>
#include <stdlib.h>

static int first = 1;

void editor_run(const uint8_t *payload, uint32_t plen) {
    (void)payload; (void)plen;
    if (first) {
        first = 0;
        SetTraceLogLevel(LOG_NONE);
        InitWindow(900, 640, "Simply Editor (C/raylib)");
        SetTargetFPS(60);
        /* 当前块 toks 载入内存（editor 拥有，动态读取会响应） */
        size_t n = 0;
        if (!cur_get(cur_key, cur_key_len, &n)) {
            Toks ts = load_toks(cur_key, cur_key_len);
            cur_set(cur_key, cur_key_len, ts.tok, ts.n);
        }
    }
    /* 每帧渲染 */
    BeginDrawing();
    ClearBackground(RAYWHITE);
    DrawText("ESC = 退出", 20, 16, 16, GRAY);
    char cur[96]; uint32_t cl = cur_key_len < 90 ? cur_key_len : 90;
    memcpy(cur, cur_key ? cur_key : (const uint8_t*)"(boot)", cur_key ? cl : 6);
    cur[cur_key ? cl : 6] = 0;
    DrawText(cur, 20, 40, 16, DARKGRAY);
    size_t n = 0;
    Tok *toks = cur_get(cur_key, cur_key_len, &n);
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
    run_next();                        /* 自主接棒（rerun 循环回 editor 每帧） */
}
