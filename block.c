// block.c —— 执行器：runblock 下钻循环（用户结构）
// runblock：
//   for (;;){
//     if (imp = hit(key))break;             命中插件 → imp = 插件，回 vm
//     *(void **)retpoint = ptr;             压返回点（当前 token 位置）
//     retpoint += 8;
//     ptr = getfirstdata(key);              ptr = 块的第一个 data
//     key = (KEY){(u32 *)ptr, ptr + 4};     key = 第一条 token（n 指向 u32 大小，d 指向数据）
//   }
// 内存变动同步（补上）：
//   - 命中后：payload 深拷贝到全局 + imp 写入 vm.exe 导出的变量
//   - 块 token 流走完（0 长 name 结束符）→ 弹返回点回上层；全部走完 → imp=NULL
//   - 弹回后推进到该 token 的下一条（继续接棒）；块起点栈同步压/弹
//   - 块数据按需取（内存 cur 优先 / server）；当前块 key 深拷贝（editor 用）
// 零错误处理：不检查任何返回值、不防御非预期
#include "simply.h"
#include <windows.h>
#include <stdlib.h>
#include <string.h>

typedef uint32_t u32;

/* key：data 结构体，一个 u32 大小一个 ptr（n 指向 u32 大小字段，d 指向数据） */
typedef struct { const u32 *n; const uint8_t *d; } KEY;

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
static void (*hit(KEY k))(void) {
    u32 n = *k.n;
    for (size_t i = 0; i < PLUGINS_N; i++) {
        size_t ln = strlen(PLUGINS[i].name);
        if (ln == n && memcmp(PLUGINS[i].name, k.d, n) == 0) return PLUGINS[i].run;
    }
    return NULL;
}

/* ================= 全局状态 ================= */
static KEY key;                        /* 当前 token（n 指向 u32 大小，d 指向数据） */
static const uint8_t *ptr;             /* 当前 token 在块数据中的位置（指向 nlen 字段） */
static const uint8_t *blk;             /* 当前块数据起点（reset 用） */
uint8_t *cur_key = NULL; u32 cur_key_len = 0;   /* 当前块 key（editor 用） */
const uint8_t *payload; u32 plen;                /* 当前插件 payload（插件内部读） */
static void (*imp)(void);              /* 当前插件（命中后写 vm.exe 导出的 imp） */

/* 返回点栈：每项 8B = 保存的 ptr；块起点栈同步压/弹 */
static void *ret_slots[256]; static void **retpoint = ret_slots; static u32 ret_n = 0;
static const uint8_t *blk_slots[256];
static int booted = 0;                 /* 入口是否已初始化 */

/* ================= 块 token 流（内存 cur 优先 / server 兜底） ================= */
/* 解析 server 原始字节 → tok 数组（name/payload 指向 blk 内）；0 长 name = 块结束 */
static size_t iter_tokens(const uint8_t *blk, u32 blen, Tok *out, size_t cap) {
    u32 i = 0; size_t n = 0;
    while (i + 4 <= blen) {
        u32 nl; memcpy(&nl, blk + i, 4); i += 4;
        if (!nl) break;                                    /* 块结束符 */
        out[n].name = (uint8_t*)blk + i; out[n].nlen = nl; i += nl;
        u32 dl; memcpy(&dl, blk + i, 4); i += 4;
        out[n].payload = (uint8_t*)blk + i; out[n].plen = dl; i += dl;
        n++;
    }
    (void)cap;
    return n;
}

/* 取块 token 流：内存 cur（editor 实时编辑）优先，否则 fetch server 解析；
   空 key（klen==0）= 引导，只取第一条 name */
Toks load_toks(const uint8_t *key, u32 klen) {
    Toks ts = {0};
    size_t n = 0;
    Tok *m = cur_get(key, klen, &n);
    if (m) { ts.tok = m; ts.n = n; ts.cap = n; ts.owned = 0; return ts; }   /* 内存 cur：editor 拥有 */

    u32 blen = 0;
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

/* getfirstdata(key)：取块的第一个 data（内存 cur 优先 / server），统一序列化为原始字节 */
static const uint8_t *getfirstdata(KEY k) {
    Toks ts = load_toks(k.d, *k.n);
    u32 sz = 4;                                        /* 结束符 */
    for (size_t i = 0; i < ts.n; i++) sz += 4 + ts.tok[i].nlen + 4 + ts.tok[i].plen;
    uint8_t *buf = (uint8_t*)malloc(sz);
    u32 off = 0;
    for (size_t i = 0; i < ts.n; i++) {
        memcpy(buf + off, &ts.tok[i].nlen, 4); off += 4;
        memcpy(buf + off, ts.tok[i].name, ts.tok[i].nlen); off += ts.tok[i].nlen;
        memcpy(buf + off, &ts.tok[i].plen, 4); off += 4;
        memcpy(buf + off, ts.tok[i].payload, ts.tok[i].plen); off += ts.tok[i].plen;
    }
    u32 z = 0; memcpy(buf + off, &z, 4);
    free_fetched(&ts);
    return buf;
}

/* ================= vm imp（GetProcAddress 写 vm 导出的 imp） ================= */
/* 取 vm.exe 导出的 imp 变量地址（缓存） */
static void (**vm_imp)(void) = NULL;
static void **get_vm_imp(void) {
    if (!vm_imp) vm_imp = (void (**)(void))GetProcAddress(GetModuleHandle(NULL), "imp");
    return (void**)vm_imp;
}

/* 命中后设插件：payload 深拷贝到全局；imp 写入 vm.exe 导出的变量 */
static void commit_imp(void) {
    u32 pl = *(u32*)(key.d + *key.n);
    const uint8_t *pay = key.d + *key.n + 4;
    free((void*)payload);
    payload = (uint8_t*)malloc(pl);
    memcpy((void*)payload, pay, pl);
    plen = pl;
    *get_vm_imp() = imp;
}

/* 当前块 key 深拷贝（editor 显示/编辑用） */
static void set_cur_key(const uint8_t *d, u32 n) {
    free(cur_key);
    cur_key = (uint8_t*)malloc(n);
    memcpy(cur_key, d, n);
    cur_key_len = n;
}

/* ================= 返回点栈 ================= */
/* 弹返回点回上层：释放子块数据、恢复父块起点，并推进到弹回 token 的下一条 */
static int pop_ret(void) {
    if (!ret_n) return 0;
    free((void*)blk);                                    /* 释放刚走完的子块数据 */
    ret_n--;
    retpoint = ret_slots + ret_n;
    ptr = (const uint8_t*)ret_slots[ret_n];              /* 弹回：块引用 token 的位置 */
    blk = blk_slots[ret_n];
    key = (KEY){(u32*)ptr, ptr + 4};                     /* 弹回的 token */
    ptr = (const uint8_t*)key.d + *key.n + 4 + *(u32*)((const uint8_t*)key.d + *key.n);  /* 推进到下一 token */
    key = (KEY){(u32*)ptr, ptr + 4};                     /* key = 下一 token */
    return 1;
}

/* ================= runblock：下钻循环（用户结构） ================= */
static void runblock(void) {
    for (;;) {
        if (imp = hit(key)) break;                       /* hit(key) → imp = 插件，回 vm */
        if (*(u32*)ptr == 0) {                           /* 内存同步：块走完 → 弹返回点 */
            if (!pop_ret()) { *get_vm_imp() = NULL; return; }   /* 全部走完 → imp=NULL */
            continue;
        }
        *(void**)retpoint = (void*)ptr;                   /* *(void**)retpoint = ptr */
        retpoint += 8;                                   /* retpoint += 8 */
        blk_slots[ret_n++] = blk;                        /* 内存同步：压当前块起点 */
        set_cur_key(key.d, *key.n);                      /* 内存同步：当前块 key（editor 用） */
        ptr = getfirstdata(key);                         /* ptr = getfirstdata(key)：块的第一个 data */
        blk = ptr;                                       /* 内存同步：当前块起点 */
        key = (KEY){(u32*)ptr, ptr + 4};                 /* key = 第一条 token */
    }
    commit_imp();                                        /* 内存同步：命中后设插件 */
}

/* ================= 入口 / 下钻 / 接棒 ================= */
/* 入口 + 插件下钻：首次（booted==0）初始化并从空 key 引导；
   否则压返回点 + 切到 key 指向的块；最终都进 runblock 下钻循环 */
void run_block(const uint8_t *d, u32 n) {
    if (!booted) {                                       /* 入口（vm: run_block(0,0)） */
        booted = 1;
        retpoint = ret_slots; ret_n = 0;
        cur_key = NULL; cur_key_len = 0;
        u32 zero = 0; key.d = NULL; key.n = &zero;       /* 空 key */
        ptr = getfirstdata(key);                        /* 空 key → 引导块第一条 */
        blk = ptr;
        key = (KEY){(u32*)ptr, ptr + 4};
        runblock();
        return;                                          /* 回 vm：for(;;){imp()} */
    }
    *(void**)retpoint = (void*)ptr; retpoint += 8;       /* 插件下钻：压返回点（当前插件 token） */
    blk_slots[ret_n++] = blk;
    set_cur_key(d, n);                                   /* 当前块 key = 目标 key */
    u32 sz = n; key.d = d; key.n = &sz;
    ptr = getfirstdata(key);                            /* 取目标块第一个 data */
    blk = ptr;
    key = (KEY){(u32*)ptr, ptr + 4};
    runblock();
}

/* 插件接棒：跳过当前 token，key = 下一 token，进 runblock */
void run_next(void) {
    ptr = (const uint8_t*)key.d + *key.n + 4 + *(u32*)((const uint8_t*)key.d + *key.n);
    key = (KEY){(u32*)ptr, ptr + 4};
    runblock();
}

/* 重跑当前块：重新取块数据（内存 cur 优先 → 编辑立即响应），进 runblock */
void reset(void) {
    free((void*)blk);
    u32 sz = cur_key_len;
    KEY bk = (KEY){&sz, cur_key};
    ptr = getfirstdata(bk);
    blk = ptr;
    key = (KEY){(u32*)ptr, ptr + 4};
    runblock();
}
