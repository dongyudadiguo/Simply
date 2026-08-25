/* token="[" -> sha256 -> 245843abef9e72e7efac30138a994bf6301e7e1d7d7042a33d42e863d2638811.dll  （参考 add.c 的插件结构） */
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
    void (*load_names)(const uint8_t*, u32, uint8_t (*)[64], u32*, u32);
    int (*net_upload_fn)(const uint8_t*, u32, const uint8_t*, u32);
    void (*heat_add)(const uint8_t*, u32);
    u32 (*heat_get)(const uint8_t*, u32);
} BlockAPI;
extern void *GetModuleHandleA(const char *name);
extern void *GetProcAddress(void *module, const char *name);
static inline BlockAPI *block_import(void) {
    typedef BlockAPI *(*fn)(void);
    return ((fn)GetProcAddress(GetModuleHandleA("block.dll"), "block_api"))();
}
#include <string.h>
#include <stdlib.h>
#include <stdio.h>


/* ---- 栈助手（对齐 add.c 的取/存约定） ---- */
static u32 pop_u32(BlockAPI *B) { *B->stk_off -= 4; u32 v; memcpy(&v, B->stk + *B->stk_off, 4); return v; }
static uintptr_t pop_ptr(BlockAPI *B) { *B->stk_off -= 8; uintptr_t v; memcpy(&v, B->stk + *B->stk_off, 8); return v; }
static void push_u32(BlockAPI *B, u32 v) { B->push((const uint8_t*)&v, 4); B->write_num(4); }
static void push_ptr(BlockAPI *B, const void *p) { B->push((const uint8_t*)&p, 8); B->write_num(8); }
static void push_bytes(BlockAPI *B, const void *p, u32 n) { B->push((const uint8_t*)p, n); B->write_num(n); }

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();

    u32 a = pop_u32(B);
    push_u32(B, a);                  /* 占位 */
    B->run_next();

}
