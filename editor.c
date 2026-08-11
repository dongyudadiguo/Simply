// editor.c —— 图形编辑器插件（raylib，内建编译进 vm）
#include <stdint.h>
#include <stddef.h>

typedef uint32_t u32;
typedef struct { uint8_t *name; uint32_t nlen; uint8_t *payload; uint32_t plen; } Tok;
typedef struct { Tok *tok; size_t n, cap, owned; } Toks;
typedef struct { u32 n; const uint8_t *d; } data;
typedef struct {
    uint8_t *stk; uint32_t *stk_off;
    uint8_t *num; uint32_t *num_off;
    uint8_t *var; uint32_t *var_off;
    void (*push)(const uint8_t*, u32);
    void (*write_num)(u32);
    void (*cur_set)(const uint8_t*, u32, Tok*, size_t);
    Tok *(*cur_get)(const uint8_t*, u32, size_t*);
    void (*hand_set)(const uint8_t*, uint8_t, uint8_t);
    void (*hand_get)(const uint8_t*, uint8_t*, uint8_t*);
    void (*run_next)(void);
    void (*reset)(void);
    void (*drill)(data);
    void (*cur_payload)(const uint8_t**, u32*);
    void (*cur_key_of)(const uint8_t**, u32*);
    Toks (*load_toks)(const uint8_t*, u32);
} BlockAPI;
extern void *GetModuleHandleA(const char *name);
extern void *GetProcAddress(void *module, const char *name);
static inline BlockAPI *block_import(void) {
    typedef BlockAPI *(*fn)(void);
    return ((fn)GetProcAddress(GetModuleHandleA("block.dll"), "block_api"))();
}
#include "raylib.h"
#include <string.h>
#include <stdlib.h>

static int first = 1;

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    /* 当前块 key 从返回栈顶读（写进 retpoint 的合成 token） */
    const uint8_t *ck; uint32_t ckl;
    B->cur_key_of(&ck, &ckl);
    if (first) {
        first = 0;
        SetTraceLogLevel(LOG_NONE);
        InitWindow(900, 640, "Simply Editor (C/raylib)");
        SetTargetFPS(60);
        /* 当前块 toks 载入内存（editor 拥有，动态读取会响应） */
        size_t n = 0;
        if (!B->cur_get(ck, ckl, &n)) {
            Toks ts = B->load_toks(ck, ckl);
            B->cur_set(ck, ckl, ts.tok, ts.n);
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
    Tok *toks = B->cur_get(ck, ckl, &n);
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

    B->reset();                       /* editor 接棒 = rerun：重跑当前块（零大小 data = editor） */
}
