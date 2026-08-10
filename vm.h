#ifndef VM_H
#define VM_H
#include <stdint.h>
#include <stddef.h>

#define VM_PORT 8000
#define PLUGIN_DIR "plugins"

typedef struct VM VM;

/* ---- token / 块 ---- */
typedef struct { uint8_t *name; uint32_t nlen; uint8_t *payload; uint32_t plen; } Tok;
typedef struct { Tok *tok; size_t n, cap; int owned; } Toks;   /* owned=1 fetch 需释放；0 内存 cur 不动 */

/* vmstate.cur 表项（key -> toks，editor 维护，block 读） */
typedef struct CurEntry { uint8_t *key; uint32_t klen; Toks toks; struct CurEntry *next; } CurEntry;
/* 插件缓存表项 */
typedef struct PluginEnt { uint8_t *name; uint32_t nlen; void *lib; void (*run)(VM*, const uint8_t*, uint32_t); struct PluginEnt *next; } PluginEnt;
/* 返回栈项（key, i 对 —— 不存 token 快照，动态读） */
typedef struct { uint8_t *key; uint32_t klen; uint32_t i; } RetItem;
/* handrun flags：id(8B) -> b1,b2 */
typedef struct HandFlag { uint8_t id[8]; uint8_t b1, b2; struct HandFlag *next; } HandFlag;

/* ---- 插件回调（插件 dll 通过 vm 指针调用，不链接主程序符号） ---- */
typedef void (*CB_run_next)(VM*);
typedef void (*CB_reset)(VM*);
typedef void (*CB_run_block)(VM*, const uint8_t*, uint32_t);
typedef void (*CB_push)(VM*, const uint8_t*, uint32_t);
typedef const uint8_t* (*CB_pop)(VM*, uint32_t);
typedef void (*CB_write_num)(VM*, uint32_t);
typedef uint8_t* (*CB_fetch)(const uint8_t*, uint32_t, uint32_t*);
typedef int  (*CB_upload)(const uint8_t*, uint32_t, const uint8_t*, uint32_t);
typedef uint32_t* (*CB_cur_toks)(VM*, uint32_t *out_n);   /* 取当前块内存 toks（editor 用） */
typedef void (*CB_hand_set)(VM*, const uint8_t*, uint8_t, uint8_t);
typedef void (*CB_hand_get)(VM*, const uint8_t*, uint8_t*, uint8_t*);
typedef Tok* (*CB_cur_get)(VM*, const uint8_t*, uint32_t, size_t*);
typedef void (*CB_cur_set)(VM*, const uint8_t*, uint32_t, Tok*, size_t);
typedef Toks (*CB_load_toks)(VM*, const uint8_t*, uint32_t);

struct VM {
    /* ---- vmstate ---- */
    uint8_t stk[4096]; uint32_t stk_off;      /* 值栈 */
    uint8_t num[512];  uint32_t num_off;      /* 大小区 */
    uint8_t var[8192]; uint32_t var_off;      /* 变量区 */
    CurEntry *cur;                            /* 当前块内容表 */
    uint8_t *cur_key; uint32_t cur_key_len;   /* 当前块 key */
    /* ---- 迭代 ---- */
    uint32_t cur_i;
    RetItem *ret; uint32_t ret_n, ret_cap;
    /* ---- 插件 ---- */
    HandFlag *hand;                               /* handrun flags 表 */
    PluginEnt *plugins;
    void (*imp)(VM*, const uint8_t*, uint32_t);   /* 当前插件 */
    const uint8_t *imp_payload; uint32_t imp_plen;
    uint8_t *imp_payload_buf;                         /* payload 深拷贝（exec 期间有效） */
    /* ---- 回调 ---- */
    CB_run_next cb_run_next; CB_reset cb_reset; CB_run_block cb_run_block;
    CB_push cb_push; CB_pop cb_pop; CB_write_num cb_write_num;
    CB_fetch cb_fetch; CB_upload cb_upload;
    CB_hand_set cb_hand_set; CB_hand_get cb_hand_get;
    CB_cur_get cb_cur_get; CB_cur_set cb_cur_set; CB_load_toks cb_load_toks;
};

/* ---- block.c ---- */
void block_init(VM *vm);
int  find_plugin(VM *vm);                    /* 下钻找下一个命中插件的 token，设 imp */
void run_block(VM *vm, const uint8_t *key, uint32_t klen);   /* 入口(ret==NULL)或下钻 */
void run_next(VM *vm);                       /* 纯推进，更新 imp */
void reset(VM *vm);                          /* 重跑当前块 */
Toks load_toks(VM *vm, const uint8_t *key, uint32_t klen);   /* 每次现取（内存 cur 优先） */
void *load_plugin(VM *vm, const uint8_t *name, uint32_t nlen);
void sha256_hex(const uint8_t *msg, uint32_t mlen, char *hex);

/* ---- vmstate.c ---- */
void vms_push(VM *vm, const uint8_t *d, uint32_t n);
const uint8_t *vms_pop(VM *vm, uint32_t n);
void vms_write_num(VM *vm, uint32_t sz);
void vms_cur_set(VM *vm, const uint8_t *key, uint32_t klen, Tok *toks, size_t n); /* 接管所有权 */
Tok *vms_cur_get(VM *vm, const uint8_t *key, uint32_t klen, size_t *out_n);
void vms_hand_set(VM *vm, const uint8_t *id, uint8_t b1, uint8_t b2);
void vms_hand_get(VM *vm, const uint8_t *id, uint8_t *b1, uint8_t *b2);

/* ---- net.c ---- */
int net_init(void);
uint8_t *net_fetch(const uint8_t *key, uint32_t klen, uint32_t *out_len); /* malloc，失败 NULL */
int net_upload(const uint8_t *key, uint32_t klen, const uint8_t *data, uint32_t dlen);
#endif
