// upload_boot.c —— 上传空 key 编辑器块（现有 token 流组成；零长名 token 的下钻目标）+ 子块
// 空 key 编辑器块（每帧）：
//   GET(inited) ! cond(editor_init)          —— 全局变量一次性初始化
//   BeginDrawing push_payload(C_BG) ClearBackground EndDrawing
//   WindowShouldClose cond(quit)             —— 关窗/ESC 退出（quit = push_int(0) exit）
//   rerun                                    —— 重跑本块 = 下一帧
// editor_init：SetTraceLogLevel(0) InitWindow(1000,700) SetTargetFPS(60) SET(inited)=1
#include "simply.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* 写一条 token：[nlen][name][plen][payload] */
static void tok(uint8_t *b, uint32_t *off, const char *name, const uint8_t *pay, uint32_t plen) {
    uint32_t nl = (uint32_t)strlen(name);
    memcpy(b + *off, &nl, 4); *off += 4;
    memcpy(b + *off, name, nl); *off += nl;
    memcpy(b + *off, &plen, 4); *off += 4;
    if (plen) { memcpy(b + *off, pay, plen); *off += plen; }
}
static void endmk(uint8_t *b, uint32_t *off) { uint32_t z = ENDMK; memcpy(b + *off, &z, 4); *off += 4; }

int main(void) {
    net_init();
    uint8_t buf[8192]; uint32_t off;
    const uint8_t none[] = {0};
    const uint8_t color[] = {15, 18, 24, 255};          /* C_BG */

    /* 空 key = 编辑器主循环块 */
    off = 0;
    tok(buf, &off, "GET", (const uint8_t*)"inited", 6);
    tok(buf, &off, "!", none, 0);
    tok(buf, &off, "cond", (const uint8_t*)"editor_init", 11);
    tok(buf, &off, "BeginDrawing", none, 0);
    tok(buf, &off, "push_payload", color, 4);
    tok(buf, &off, "ClearBackground", none, 0);
    tok(buf, &off, "EndDrawing", none, 0);
    tok(buf, &off, "WindowShouldClose", none, 0);
    tok(buf, &off, "cond", (const uint8_t*)"quit", 4);
    tok(buf, &off, "rerun", none, 0);
    endmk(buf, &off);
    net_upload((const uint8_t*)"", 0, buf, off);

    /* editor_init 块：一次性初始化（SET 全局变量 inited=1 后再不进） */
    off = 0;
    tok(buf, &off, "push_int", (const uint8_t*)"0\0", 2);
    tok(buf, &off, "SetTraceLogLevel", none, 0);
    tok(buf, &off, "push_int", (const uint8_t*)"1000\0", 5);   /* InitWindow 插件先 pop h 再 pop w */
    tok(buf, &off, "push_int", (const uint8_t*)"700\0", 4);
    tok(buf, &off, "InitWindow", none, 0);
    tok(buf, &off, "push_int", (const uint8_t*)"60\0", 3);
    tok(buf, &off, "SetTargetFPS", none, 0);
    tok(buf, &off, "push_int", (const uint8_t*)"1\0", 2);
    tok(buf, &off, "SET", (const uint8_t*)"inited", 6);
    endmk(buf, &off);
    net_upload((const uint8_t*)"editor_init", 11, buf, off);

    /* quit 块：exit(0) */
    off = 0;
    tok(buf, &off, "push_int", (const uint8_t*)"0\0", 2);
    tok(buf, &off, "exit", none, 0);
    endmk(buf, &off);
    net_upload((const uint8_t*)"quit", 4, buf, off);

    printf("上传 空 key 编辑器块 + editor_init + quit\n");
    return 0;
}
