// block.c —— 执行器：全局状态 + 尾调用连续执行（命中→imp；否则压返回点取第一个data）
#include "api.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

/* ---------------- 插件表（内建，逻辑名 → 函数，编译进 vm） ---------------- */
typedef struct { const char *name; void (*run)(const uint8_t*, uint32_t); } Plugin;
static const Plugin PLUGINS[] = {
    {"boot", boot_run}, {"editor", editor_run}, {"rerun", rerun_run},
    {"add", add_run}, {"read", read_run}, {"set", set_run},
    {"cond", cond_run}, {"handrun", handrun_run}, {"condrerun", condrerun_run},
    {"push_int", push_int_run}, {"in-int", in_int_run}, {"out", out_run},
    {"rand", rand_run}, {"gt", gt_run}, {"lt", lt_run}, {"eq", eq_run},
    {"mul", mul_run}, {"ret_int", ret_int_run},
};
#define PLUGINS_N (sizeof(PLUGINS)/sizeof(PLUGINS[0]))

static void *load_plugin(const uint8_t *name, uint32_t nlen) {   /* 命中插件 → run；否则 NULL（块引用） */
    for (size_t i = 0; i < PLUGINS_N; i++) {
        size_t ln = strlen(PLUGINS[i].name);
        if (ln == nlen && memcmp(PLUGINS[i].name, name, nlen) == 0) return (void*)PLUGINS[i].run;
    }
    return NULL;
}

/* ---------------- token 流解析 ---------------- */
static size_t iter_tokens(const uint8_t *blk, uint32_t blen, Tok *out, size_t cap) {
    uint32_t i = 0; size_t n = 0;
    while (i + 4 <= blen) {
        uint32_t nl; memcpy(&nl, blk + i, 4); i += 4;
        if (!nl) break;
        if (i + nl > blen) break;
        out[n].name = (uint8_t*)blk + i; out[n].nlen = nl; i += nl;
        if (i + 4 > blen) break;
        uint32_t dl; memcpy(&dl, blk + i, 4); i += 4;
        if (i + dl > blen) break;
        out[n].payload = (uint8_t*)blk + i; out[n].plen = dl; i += dl;
        n++;
    }
    (void)cap;
    return n;
}

/* 动态取块 token 流：内存 cur 优先（editor 实时维护），否则 fetch server 解析（不固化，每次现取） */
Toks load_toks(const uint8_t *key, uint32_t klen) {
    Toks ts = {0};
    size_t n = 0;
    Tok *m = cur_get(key, klen, &n);
    if (m) { ts.tok = m; ts.n = n; ts.cap = n; ts.owned = 0; return ts; }   /* 内存优先：改动立即响应，不释放 */

    uint32_t blen = 0;
    uint8_t *blk = net_fetch(key, klen, &blen);
    if (!blk) return ts;

    if (klen == 0) {                                         /* 引导：空 key 只取第一条 name */
        Tok tmp[1];
        if (iter_tokens(blk, blen, tmp, 1) > 0) {
            ts.tok = (Tok*)calloc(1, sizeof(Tok));
            ts.n = ts.cap = 1; ts.owned = 1;
            ts.tok[0].name = (uint8_t*)malloc(tmp[0].nlen);
            memcpy(ts.tok[0].name, tmp[0].name, tmp[0].nlen);
            ts.tok[0].nlen = tmp[0].nlen;
            ts.tok[0].payload = NULL; ts.tok[0].plen = 0;
        }
        free(blk);
        return ts;
    }

    Tok tmp[256];
    size_t cnt = iter_tokens(blk, blen, tmp, 256);
    ts.tok = (Tok*)calloc(cnt ? cnt : 1, sizeof(Tok));
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

static void free_fetched(Toks *ts) {
    if (!ts->owned) { ts->tok = NULL; ts->n = ts->cap = 0; return; }   /* 内存 cur：editor 拥有，不释放 */
    if (ts->tok) {
        for (size_t k = 0; k < ts->n; k++) {
            free(ts->tok[k].name);
            if (ts->tok[k].payload) free(ts->tok[k].payload);
        }
        free(ts->tok);
    }
    ts->tok = NULL; ts->n = ts->cap = 0;
}

/* ---------------- 执行核心：全局状态 + 尾调用 ---------------- */
uint8_t *cur_key = NULL; uint32_t cur_key_len = 0;      /* 当前块 key（editor 用） */
static uint32_t cur_i = 0;                               /* 当前 token 位置 */
typedef struct { uint8_t *key; uint32_t klen; uint32_t i; } RetItem;
static RetItem *ret = NULL; static uint32_t ret_n = 0;  /* 返回点栈 */
static void (*imp)(const uint8_t*, uint32_t) = NULL;    /* 当前插件 */
static const uint8_t *imp_payload; static uint32_t imp_plen;
static uint8_t *imp_payload_buf = NULL;

/* 下钻循环（token 从空 key（大小为零）开始；命中→设 imp；否则压返回点 + 取块的第一个 data） */
static int find_plugin(void) {
    for (;;) {
        Toks ts = load_toks(cur_key, cur_key_len);            /* 每次现取（内存改动立即响应） */
        if (cur_i >= ts.n) {                                  /* 当前块 token 走完 */
            free_fetched(&ts);
            if (ret_n) {                                      /* 弹返回点回上层 */
                RetItem *r = &ret[--ret_n];
                if (cur_key) free(cur_key);
                cur_key = r->key; cur_key_len = r->klen; cur_i = r->i;
                continue;
            }
            imp = NULL;                                       /* 全部走完 → 执行链结束 */
            return 0;
        }
        Tok t = ts.tok[cur_i]; cur_i++;                       /* 取当前 token */
        void *run = load_plugin(t.name, t.nlen);              /* 命中插件？ */
        if (run) {                                            /* 命中 → 执行 */
            if (imp_payload_buf) free(imp_payload_buf);       /* payload 深拷贝（执行期间有效） */
            imp_payload_buf = NULL;
            if (t.plen) {
                imp_payload_buf = (uint8_t*)malloc(t.plen);
                memcpy(imp_payload_buf, t.payload, t.plen);
            }
            imp = run; imp_payload = imp_payload_buf; imp_plen = t.plen;
            free_fetched(&ts);
            return 1;
        }
        /* 块引用 → 压返回点 + 取块的第一个 data（下钻） */
        ret = (RetItem*)realloc(ret, (ret_n + 1) * sizeof(RetItem));
        RetItem *r = &ret[ret_n++];
        r->key = cur_key; r->klen = cur_key_len; r->i = cur_i;
        cur_key = (uint8_t*)malloc(t.nlen); memcpy(cur_key, t.name, t.nlen);
        cur_key_len = t.nlen;
        cur_i = 0;                                            /* data 开头的第一个 token */
        free_fetched(&ts);
    }
}

/* 执行链：尾调用无限连续（-O2 尾调用优化 → jump，函数栈不增长）；插件内 run_next/reset/run_block 更新 imp */
static void run_imp(void) {
    if (!imp) return;                                         /* 全部走完 */
    imp(imp_payload, imp_plen);                               /* 执行当前插件 */
    return run_imp();                                         /* 尾调用 → 接棒下一插件 */
}

/* ---------------- 入口 / 下钻 / 接棒 ---------------- */
void run_block(const uint8_t *key, uint32_t klen) {
    if (!ret) {                                               /* 入口（vm.c: run_block(NULL,0)） */
        ret = (RetItem*)malloc(sizeof(RetItem));              /* 分配返回栈（空） */
        ret_n = 0;
        cur_key = NULL; cur_key_len = 0;                      /* 从 token 大小为零开始 */
        cur_i = 0;
        find_plugin();                                        /* 下钻到首个命中插件 */
        run_imp();                                            /* 启动执行链（尾调用） */
        return;
    }
    /* 下钻（插件内回调）：压返回点 + 切块 */
    ret = (RetItem*)realloc(ret, (ret_n + 1) * sizeof(RetItem));
    RetItem *r = &ret[ret_n++];
    r->key = cur_key; r->klen = cur_key_len; r->i = cur_i;
    if (cur_key) free(cur_key);
    cur_key = (uint8_t*)malloc(klen ? klen : 1); memcpy(cur_key, key, klen);
    cur_key_len = klen;
    cur_i = 0;
    find_plugin();                                            /* 更新 imp（当前 run_imp 链继续执行） */
}

void run_next(void) { find_plugin(); }                        /* 插件自主接棒：位置已推进，更新 imp */
void reset(void)     { cur_i = 0; find_plugin(); }            /* 重跑当前块 */
