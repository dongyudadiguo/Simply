/* plug_api.h —— 新插件统一 preamble（对齐 simply.h 的 BlockAPI 字段顺序，经 block.dll GetProcAddress("block_api") 取） */
#ifndef PLUG_API_H
#define PLUG_API_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
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
    u32 (*GET)(const uint8_t*, u32);
    void (*SET)(const uint8_t*, u32, u32);
    const uint8_t *(*gv_get)(const uint8_t*, u32, u32*);
    void (*gv_set)(const uint8_t*, u32, const uint8_t*, u32);
    void (*cur_root_of)(const uint8_t**, u32*);
} BlockAPI;
extern void *GetModuleHandleA(const char *name);
extern void *GetProcAddress(void *module, const char *name);
static inline BlockAPI *block_import(void) {
    typedef BlockAPI *(*fn)(void);
    return ((fn)GetProcAddress(GetModuleHandleA("block.dll"), "block_api"))();
}
/* 栈助手（对齐 add.c 约定） */
static inline u32 pop_u32(BlockAPI *B) { *B->stk_off -= 4; u32 v; memcpy(&v, B->stk + *B->stk_off, 4); return v; }
static inline uintptr_t pop_ptr(BlockAPI *B) { *B->stk_off -= 8; uintptr_t v; memcpy(&v, B->stk + *B->stk_off, 8); return v; }
static inline void push_u32(BlockAPI *B, u32 v) { B->push((const uint8_t*)&v, 4); B->write_num(4); }
static inline void push_ptr(BlockAPI *B, const void *p) { B->push((const uint8_t*)&p, 8); B->write_num(8); }
static inline void push_bytes(BlockAPI *B, const void *p, u32 n) { B->push((const uint8_t*)p, n); B->write_num(n); }
#endif
