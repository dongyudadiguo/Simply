// vmstate.c —— 运行时共享状态（全局，对齐 vmstate.py）
#include "simply.h"
#include <stdlib.h>
#include <string.h>

uint8_t stk[4096]; uint32_t stk_off;
uint8_t num[512];  uint32_t num_off;
uint8_t var[8192]; uint32_t var_off;

void push(const uint8_t *d, uint32_t n) { memcpy(stk + stk_off, d, n); stk_off += n; }
const uint8_t *pop(uint32_t n) { stk_off -= n; return stk + stk_off; }
void write_num(uint32_t sz) {
    if (num_off + 4 > sizeof(num)) { num_off = sizeof(num) - 4; return; } /* 防溢出：num 只被 set 消费；循环推值不消费时钳在末位 */
    memcpy(num + num_off, &sz, 4); num_off += 4;
}

/* 内存块表（key -> toks，editor 维护，block 动态读） */
typedef struct CurEntry { uint8_t *key; uint32_t klen; Toks toks; struct CurEntry *next; } CurEntry;
static CurEntry *cur_list;
void cur_set(const uint8_t *key, uint32_t klen, Tok *toks, size_t n) {
    CurEntry *e = cur_list;
    while (e) { if (e->klen == klen && memcmp(e->key, key, klen) == 0) break; e = e->next; }
    if (!e) {
        e = (CurEntry*)calloc(1, sizeof(CurEntry));
        e->key = (uint8_t*)malloc(klen); memcpy(e->key, key, klen); e->klen = klen;
        e->next = cur_list; cur_list = e;
    } else free(e->toks.tok);
    e->toks.tok = toks; e->toks.n = n; e->toks.cap = n;
    cur_mark(key, klen);                             /* 内存有变动 → 标记待上传 */
}
Tok *cur_get(const uint8_t *key, uint32_t klen, size_t *out_n) {
    CurEntry *e = cur_list;
    while (e) {
        if (e->klen == klen && memcmp(e->key, key, klen) == 0) { *out_n = e->toks.n; return e->toks.tok; }
        e = e->next;
    }
    *out_n = 0; return NULL;
}

/* 内存变动标记：editor 编辑（cur_set）后置脏，runblock 检测到就上传 server */
static uint8_t *dirty_key = NULL; static uint32_t dirty_len = 0; static int dirty = 0;
void cur_mark(const uint8_t *key, uint32_t klen) {
    dirty = 1;
    free(dirty_key); dirty_key = (uint8_t*)malloc(klen); memcpy(dirty_key, key, klen); dirty_len = klen;
}
int cur_dirty(const uint8_t *key, uint32_t klen) {
    return dirty && dirty_len == klen && memcmp(dirty_key, key, klen) == 0;
}
void cur_clean(void) { dirty = 0; }

/* handrun flags（id 8B -> b1,b2） */
typedef struct HandFlag { uint8_t id[8]; uint8_t b1, b2; struct HandFlag *next; } HandFlag;
static HandFlag *hand_list;
void hand_set(const uint8_t *id, uint8_t b1, uint8_t b2) {
    HandFlag *h = hand_list;
    while (h) { if (memcmp(h->id, id, 8) == 0) { h->b1 = b1; h->b2 = b2; return; } h = h->next; }
    h = (HandFlag*)calloc(1, sizeof(HandFlag));
    memcpy(h->id, id, 8); h->b1 = b1; h->b2 = b2;
    h->next = hand_list; hand_list = h;
}
void hand_get(const uint8_t *id, uint8_t *b1, uint8_t *b2) {
    HandFlag *h = hand_list;
    while (h) { if (memcmp(h->id, id, 8) == 0) { *b1 = h->b1; *b2 = h->b2; return; } h = h->next; }
    *b1 = *b2 = 0;
}

/* 全局变量（GET/SET token）：名字 → u32 值。进程级持久，缺失默认 0；与 var 区（set/read 栈上登记）独立 */
typedef struct GVar { uint8_t *name; u32 nlen; u32 val; struct GVar *next; } GVar;
static GVar *g_list;
u32 GET(const uint8_t *name, u32 nlen) {
    GVar *g = g_list;
    while (g) { if (g->nlen == nlen && memcmp(g->name, name, nlen) == 0) return g->val; g = g->next; }
    return 0;                                            /* 缺失默认 0 */
}
void SET(const uint8_t *name, u32 nlen, u32 v) {
    GVar *g = g_list;
    while (g) { if (g->nlen == nlen && memcmp(g->name, name, nlen) == 0) { g->val = v; return; } g = g->next; }
    g = (GVar*)calloc(1, sizeof(GVar));
    g->name = (uint8_t*)malloc(nlen ? nlen : 1); memcpy(g->name, name, nlen); g->nlen = nlen;
    g->val = v;
    g->next = g_list; g_list = g;
}

/* 热力计数（cond/handrun/condrerun 执行次数，editor 显示热力高亮） */
typedef struct Heat { uint8_t name[64]; u32 nlen; u32 count; struct Heat *next; } Heat;
static Heat *heat_list;
void heat_add(const uint8_t *name, u32 nlen) {
    Heat *h = heat_list;
    while (h) { if (h->nlen == nlen && memcmp(h->name, name, nlen) == 0) { h->count++; return; } h = h->next; }
    h = (Heat*)calloc(1, sizeof(Heat));
    u32 c = nlen < 64 ? nlen : 64; memcpy(h->name, name, c); h->nlen = c; h->count = 1;
    h->next = heat_list; heat_list = h;
}
u32 heat_get(const uint8_t *name, u32 nlen) {
    Heat *h = heat_list;
    while (h) { if (h->nlen == nlen && memcmp(h->name, name, nlen) == 0) return h->count; h = h->next; }
    return 0;
}
