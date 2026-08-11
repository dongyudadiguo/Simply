#ifndef API_H
#define API_H
#define VM_PORT 8000
#include <stdint.h>
#include <stddef.h>

/* ---- 块 token（数据容器，非 VM 结构体） ---- */
typedef struct { uint8_t *name; uint32_t nlen; uint8_t *payload; uint32_t plen; } Tok;
typedef struct { Tok *tok; size_t n, cap, owned; } Toks;

/* ---- vmstate 全局 ---- */
extern uint8_t stk[4096]; extern uint32_t stk_off;    /* 值栈 */
extern uint8_t num[512];  extern uint32_t num_off;    /* 大小区 */
extern uint8_t var[8192]; extern uint32_t var_off;    /* 变量区 */
void push(const uint8_t *d, uint32_t n);
const uint8_t *pop(uint32_t n);
void write_num(uint32_t sz);
void cur_set(const uint8_t *key, uint32_t klen, Tok *toks, size_t n);   /* 内存块表（editor 维护） */
Tok *cur_get(const uint8_t *key, uint32_t klen, size_t *out_n);
void cur_mark(const uint8_t *key, uint32_t klen);                         /* 标记该块内存有变动（待上传） */
int cur_dirty(const uint8_t *key, uint32_t klen);                         /* 该块是否有变动待上传 */
void cur_clean(void);                                                      /* 已上传，清标记 */
void hand_set(const uint8_t *id, uint8_t b1, uint8_t b2);               /* handrun flags */
void hand_get(const uint8_t *id, uint8_t *b1, uint8_t *b2);

/* ---- 网络 ---- */
int net_init(void);
uint8_t *net_fetch(const uint8_t *key, uint32_t klen, uint32_t *out_len);  /* malloc，失败 NULL */
int net_upload(const uint8_t *key, uint32_t klen, const uint8_t *data, uint32_t dlen);

/* ---- block 执行器（全局） ---- */
extern const uint8_t *payload; extern uint32_t plen;   /* 当前插件 payload（插件内部读） */
void run_block(const uint8_t *key, uint32_t klen);      /* 入口 key=NULL,0 或插件下钻 */
void run_next(void);                                    /* 插件自主接棒 */
void reset(void);                                       /* 重跑当前块 */
Toks load_toks(const uint8_t *key, uint32_t klen);      /* 每次现取（内存 cur 优先/server 兜底） */

/* ---- 插件（内建函数表，编译进 vm） ---- */
void boot_run(void);
void editor_run(void);
void rerun_run(void);
void add_run(void);
void read_run(void);
void set_run(void);
void cond_run(void);
void handrun_run(void);
void condrerun_run(void);
void push_int_run(void);
void in_int_run(void);
void out_run(void);
void rand_run(void);
void gt_run(void);
void lt_run(void);
void eq_run(void);
void mul_run(void);
void ret_int_run(void);
#endif
