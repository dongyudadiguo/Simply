/* token="item_label" -> sha256 -> 5d7a2756fe66a02df53f53a0213c443ebbb6119fd18a91094ba4c225405092a9.dll  （参考 add.c 的插件结构） */
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

static int name_is(const Tok *t, const char *s) {
    size_t n = strlen(s);
    return t->nlen == n && memcmp(t->name, s, n) == 0;
}

static void item_label_impl(const Tok *t, char *out) {
    if (t->nlen == 0) { strcpy(out, "(editor)"); return; }
    if (name_is(t, "handrun")) {
        u32 pl = t->plen > 8 ? t->plen - 8 : 0;
        if (pl == 0) { strcpy(out, "handrun"); return; }
        u32 c = pl < 100 ? pl : 100;
        memcpy(out, t->payload + 8, c); out[c] = 0;
        return;
    }
    if ((name_is(t,"read")||name_is(t,"set")||name_is(t,"cond")||name_is(t,"condrerun")||name_is(t,"push_int")) && t->plen > 0) {
        u32 c = t->plen < 100 ? t->plen : 100;
        memcpy(out, t->payload, c); out[c] = 0;
        return;
    }
    u32 c = t->nlen < 100 ? t->nlen : 100;
    memcpy(out, t->name, c); out[c] = 0;
}

/* ---- 栈助手（对齐 add.c 的取/存约定） ---- */
static u32 pop_u32(BlockAPI *B) { *B->stk_off -= 4; u32 v; memcpy(&v, B->stk + *B->stk_off, 4); return v; }
static uintptr_t pop_ptr(BlockAPI *B) { *B->stk_off -= 8; uintptr_t v; memcpy(&v, B->stk + *B->stk_off, 8); return v; }
static void push_u32(BlockAPI *B, u32 v) { B->push((const uint8_t*)&v, 4); B->write_num(4); }
static void push_ptr(BlockAPI *B, const void *p) { B->push((const uint8_t*)&p, 8); B->write_num(8); }
static void push_bytes(BlockAPI *B, const void *p, u32 n) { B->push((const uint8_t*)p, n); B->write_num(n); }

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();

    char *out = (char*)pop_ptr(B);
    Tok *t = (Tok*)pop_ptr(B);
    item_label_impl(t, out);
    B->run_next();

}
