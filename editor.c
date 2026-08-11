// editor.c —— 图形编辑器插件（raylib，内建编译进 vm）
#include "simply.h"
#include "raylib.h"
#include <string.h>
#include <stdlib.h>

static int first = 1;

void editor_run(void) {
    if (first) {
        first = 0;
        SetTraceLogLevel(LOG_NONE);
        InitWindow(900, 640, "Simply Editor (C/raylib)");
        SetTargetFPS(60);
        /* 当前块 key 问题稍后处理 —— 暂不载入内存表、不显示块内容 */
    }
    /* 每帧渲染（占位：当前块稍后处理） */
    BeginDrawing();
    ClearBackground(RAYWHITE);
    DrawText("ESC = 退出", 20, 16, 16, GRAY);
    DrawText("(?) 当前块稍后处理", 20, 40, 16, DARKGRAY);
    EndDrawing();
    if (WindowShouldClose()) exit(0);
    run_next();                        /* 自主接棒（rerun 循环回 editor 每帧） */
}
