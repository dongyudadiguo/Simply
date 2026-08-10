// block.c —— 执行器：runblock 下钻循环
// runblock 语义（对齐伪代码）：
//   while(1){
//     if(hit(key)){ imp = key }           命中插件 → 设 imp（随后回 vm 执行）
//     *(void**)retpoint = ptr; retpoint+=8 压返回点
//     ptr = getfirstdata(key)              取块的第一个 data
//     key = (KEY){*(u32*)ptr, ptr+4}       下一条 token = data 开头的 size + data+4
//   }
// 我没写内存变动同步，这里加上：
//   - 块 token 流取数：内存 cur 优先 / server 兜底（load_toks）
//   - 命中 → 打破循环回 vm：for(;;){imp()}
//   - 块 token 流走完 → 弹返回点回上层；全部走完 → imp=NULL
//   - 返回点深拷贝（key + 位置）；payload 深拷贝到全局
// 零错误处理：不检查任何返回值、不防御非预期
#include "simply.h"
#include <windows.h>
#include <stdlib.h>
#include <string.h>

/* ================= 插件表（内建，逻辑名 → 函数） ================= */
typedef struct { const char *name; void (*run)(void); } Plugin;
static const Plugin PLUGINS[] = {
    {"boot", boot_run}, {"editor", editor_run}, {"rerun", rerun_run},
    {"add", add_run}, {"read", read_run}, {"set", set_run},
    {"cond", cond_run}, {"handrun", handrun_run}, {"condrerun", condrerun_run},
    {"push_int", push_int_run}, {"in-int", in_int_run}, {"out", out_run},
    {"rand", rand_run}, {"gt", gt_run}, {"lt", lt_run}, {"eq", eq_run},
    {"mul", mul_run}, {"ret_int", ret_int_run},
};
#define PLUGINS_N (sizeof(PLUGINS)/sizeof(PLUGINS[0]))

/* hit(key)：token 命中插件 → run；否则 NULL（= 块引用，下钻） */
static void (*hit(const uint8_t *name, uint32_t nlen))(void) {
    for (size_t i = 0; i < PLUGINS_N; i++) {
        size_t ln = strlen(PLUGINS[i].name);
        if (ln == nlen && memcmp(PLUGINS[i].name, name, nlen) == 0) return PLUGINS[i].run;
    }
    return NULL;
}

/* ================= 全局状态 ================= */
uint8_t *cur_key = NULL; uint32_t cur_key_len = 0;   /* 当前块 key（editor 用） */
static uint32_t cur_i = 0;                            /* 当前块 token 流位置 */
typedef struct { uint8_t *key; uint32_t klen; uint32_t i; } Ret;  /* 返回点 */
static Ret *ret = NULL; static uint32_t ret_n = 0;    /* 返回点栈 */

const uint8_t *payload; uint32_t plen;               /* 当前插件 payload（插件内部读） */

/* ================= 块 token 流（内存 cur 优先 / server 兜底） ================= */
/* 解析 server 原始字节 → tok 数组（name/payload 指向 blk 内）；0 长 name = 块结束 */
static size_t iter_tokens(const uint8_t *blk, uint32_t blen, Tok *out, size_t cap) {
    uint32_t i = 0; size_t n = 0;
    while (i + 4 <= blen) {
        uint32_t nl; memcpy(&nl, blk + i, 4); i += 4;
        if (!nl) break;                                    /* 块结束符 */
        out[n].name = (uint8_t*)blk + i; out[n].nlen = nl; i += nl;
        uint32_t dl; memcpy(&dl, blk + i, 4); i += 4;
        out[n].payload = (uint8_t*)blk + i; out[n].plen = dl; i += dl;
        n++;
    }
    (void)cap;
    return n;
}

Toks load_toks(const uint8_t *key, uint32_t klen) {
    Toks ts = {0};
    size_t n = 0;
    Tok *m = cur_get(key, klen, &n);
    if (m) { ts.tok = m; ts.n = n; ts.cap = n; ts.owned = 0; return ts; }   /* 内存 cur：editor 拥有 */

    uint32_t blen = 0;
    uint8_t *blk = net_fetch(key, klen, &blen);

    if (klen == 0) {                                         /* 引导：空 key 只取第一条 name */
        Tok tmp[1];
        iter_tokens(blk, blen, tmp, 1);
        ts.tok = (Tok*)calloc(1, sizeof(Tok));
        ts.n = ts.cap = 1; ts.owned = 1;
        ts.tok[0].name = (uint8_t*)malloc(tmp[0].nlen);
        memcpy(ts.tok[0].name, tmp[0].name, tmp[0].nlen);
        ts.tok[0].nlen = tmp[0].nlen;
        ts.tok[0].payload = NULL; ts.tok[0].plen = 0;
        free(blk);
        return ts;
    }

    Tok tmp[256];
    size_t cnt = iter_tokens(blk, blen, tmp, 256);
    ts.tok = (Tok*)calloc(cnt, sizeof(Tok));
    for (size_t k = 0; k < cnt; k++) {
        ts.tok[k].name = (uint8_t*)malloc(tmp[k].nlen);
        memcpy(ts.tok[k].name, tmp[k].name, tmp[k].nlen);
        ts.tok[k].nlen = tmp[k].nlen;
        ts.tok[k].payload = (uint8_t*)malloc(tmp[k].plen);
        memcpy(ts.tok[k].payload, tmp[k].payload, tmp[k].plen);
        ts.tok[k].plen = tmp[k].plen;
    }
    ts.n = ts.cap = cnt; ts.owned = 1;
    free(blk);
    return ts;
}

/* 释放本次 fetch 解析的 toks（内存 cur 的 toks 由 editor 拥有，不动） */
static void free_fetched(Toks *ts) {
    if (!ts->owned) { ts->tok = NULL; ts->n = ts->cap = 0; return; }
    for (size_t k = 0; k < ts->n; k++) {
        free(ts->tok[k].name);
        free(ts->tok[k].payload);
    }
    free(ts->tok);
    ts->tok = NULL; ts->n = ts->cap = 0;
}

/* ================= 返回点栈 ================= */
/* 压返回点（当前块 key + 下一位置；key 深拷贝，避免悬垂） */
static void push_return(void) {
    ret = (Ret*)realloc(ret, (ret_n + 1) * sizeof(Ret));
    ret[ret_n].key = (uint8_t*)malloc(cur_key_len);
    memcpy(ret[ret_n].key, cur_key, cur_key_len);
    ret[ret_n].klen = cur_key_len;
    ret[ret_n].i = cur_i;
    ret_n++;
}

/* 弹返回点回上层；有则恢复并返回 1，没有返回 0 */
static int pop_return(void) {
    if (!ret_n) return 0;
    Ret *r = &ret[--ret_n];
    free(cur_key);
    cur_key = r->key; cur_key_len = r->klen; cur_i = r->i;
    return 1;
}

/* ================= vm imp（GetProcAddress 写 vm 导出的 imp） ================= */
static void (**vm_imp)(void) = NULL;
static void **get_vm_imp(void) {
    if (!vm_imp) vm_imp = (void (**)(void))GetProcAddress(GetModuleHandle(NULL), "imp");
    return (void**)vm_imp;
}

/* 设当前插件：payload 深拷贝到全局；imp 写入 vm.exe 导出的变量 */
static void set_imp(void (*run)(void), const Tok *t) {
    free((void*)payload);
    payload = (uint8_t*)malloc(t->plen);
    memcpy((void*)payload, t->payload, t->plen);
    plen = t->plen;
    *get_vm_imp() = run;
}

/* ================= runblock：下钻循环 ================= */
static int runblock(void) {
    for (;;) {
        Toks toks = load_toks(cur_key, cur_key_len);      /* 取当前块的 token 流 */
        if (cur_i >= toks.n) {                            /* 块走完 → 弹返回点回上层 */
            free_fetched(&toks);
            if (!pop_return()) { *get_vm_imp() = NULL; return 0; }   /* 全部走完 → imp=NULL */
            continue;
        }
        Tok t = toks.tok[cur_i++];                        /* key = 当前 token */
        void (*run)(void) = hit(t.name, t.nlen);          /* hit(key) */
        if (run) {                                        /* 命中插件 → imp = key，回 vm */
            set_imp(run, &t);
            free_fetched(&toks);
            return 1;
        }
        push_return();                                    /* 压返回点 */
        free(cur_key);                                    /* 切块：key = 块的第一个 data */
        cur_key = (uint8_t*)malloc(t.nlen);
        memcpy(cur_key, t.name, t.nlen); cur_key_len = t.nlen; cur_i = 0;
        free_fetched(&toks);
    }
}

/* ================= 入口 / 下钻 / 接棒 ================= */
void run_block(const uint8_t *key, uint32_t klen) {
    if (!ret) {                                           /* 入口（vm: run_block(0,0)） */
        ret = (Ret*)malloc(sizeof(Ret));
        ret_n = 0; cur_key = NULL; cur_key_len = 0; cur_i = 0;
        runblock();
        return;                                           /* 回 vm：for(;;){imp()} */
    }
    push_return();                                        /* 插件下钻：压返回点 + 切块 */
    free(cur_key);
    cur_key = (uint8_t*)malloc(klen);
    memcpy(cur_key, key, klen); cur_key_len = klen; cur_i = 0;
    runblock();
}

void run_next(void) { runblock(); }                       /* 插件接棒：继续当前块下一 token */
void reset(void)     { cur_i = 0; runblock(); }           /* 重跑当前块 */
