#ifndef API_H
#define API_H
#define VM_PORT 8000
#define ENDMK 0xFFFFFFFFu   /* 块结尾标记：4 字节全 1（与 nlen=0 的 editor 零长名区分） */
#include <stdint.h>
#include <stddef.h>

typedef uint32_t u32;   /* 全项目通用（block/插件共用） */

/* data：一个 u32 大小 + 一个 ptr（n = size 值，d = 数据指针） */
typedef struct { uint32_t n; const uint8_t *d; } data;

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
void heat_add(const uint8_t *name, u32 nlen);                            /* 热力计数（插件执行上报） */
u32 heat_get(const uint8_t *name, u32 nlen);

/* ---- sha256（token → 插件 DLL 文件名） ---- */
void sha256(const uint8_t *data, uint32_t len, uint8_t out[32]);

/* ---- 网络 ---- */
int net_init(void);
uint8_t *net_fetch(const uint8_t *key, uint32_t klen, uint32_t *out_len);  /* malloc，失败 NULL */
int net_upload(const uint8_t *key, uint32_t klen, const uint8_t *data, uint32_t dlen);

/* ---- block 执行器（全局） ---- */
extern const uint8_t *ptr;                            /* 当前 token 位置（插件从它推自己 payload） */
void cur_payload(const uint8_t **out_p, uint32_t *out_n); /* 当前插件 payload = 从 ptr 推出 */
void run(void);                                          /* vm 专用入口：引导 id 后 drill(id) */
void drill(data k);                                       /* 下钻循环：插件下钻 / run_next/reset 接棒 */
void cur_key_of(const uint8_t **out_d, uint32_t *out_n);  /* 当前块 key（从返回栈顶读） */
void run_next(void);                                    /* 插件自主接棒 */
void reset(void);                                       /* 重跑当前块 */
Toks load_toks(const uint8_t *key, uint32_t klen);      /* 每次现取（内存 cur 优先/server 兜底） */

/* ---- 显式动态链接：插件运行时 GetProcAddress("block_api") 拿 block.dll 的函数/全局表 ---- */
typedef struct {
    uint8_t *stk;   uint32_t *stk_off;              /* vmstate 全局 */
    uint8_t *num;   uint32_t *num_off;
    uint8_t *var;   uint32_t *var_off;
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
    void (*load_names)(const uint8_t*, u32, uint8_t (*)[64], u32*, u32);   /* 取块全部 token 名（补全用） */
    int (*net_upload_fn)(const uint8_t*, u32, const uint8_t*, u32);        /* 上传（拖出占位用） */
    void (*heat_add)(const uint8_t*, u32);                                /* 热力计数上报 */
    u32 (*heat_get)(const uint8_t*, u32);                                 /* 热力读取 */
} BlockAPI;
BlockAPI *block_api(void);                            /* block.dll 导出（插件显式动态链接取） */
#ifndef WINAPI                                              /* windows.h 已含则用它声明；否则手动声明 kernel32 */
extern void *GetModuleHandleA(const char *name);
extern void *GetProcAddress(void *module, const char *name);
#endif
/* 插件显式动态链接：运行时从 block.dll GetProcAddress('block_api') 取函数/全局表 */
static inline BlockAPI *block_import(void) {
    typedef BlockAPI *(*fn)(void);
    return ((fn)GetProcAddress(GetModuleHandleA("block.dll"), "block_api"))();
}

#endif
