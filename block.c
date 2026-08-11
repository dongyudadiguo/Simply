// block.c —— 执行器：drill 下钻循环（用户结构）
// drill：
//   for (;;){
//     if (imp = hit(key))break;             命中插件 → imp = 插件，回 vm
//     *(void **)retpoint = ptr;             压返回点（当前 token 位置）
//     retpoint += 8;
//     ptr = getfirstdata(key);              ptr = 块的第一个 data
//     key = (data){(u32 *)ptr, ptr + 4};     key = 第一条 token（n 指向 u32 大小，d 指向数据）
//   }
// 内存变动同步（补上）：
//   - 内存 cur 有变动 → 上传 server（getfirstdata 检测到脏块就序列化 net_upload）
//   - 命中后：payload 深拷贝到全局 + imp 写入 vm.exe 导出的变量
//   - 块数据按需取（内存 cur 优先 / server），缓冲不释放
//   - 当前块 key 写进返回栈（每个下钻压 [父块位置, key合成token]），栈顶 = 当前块 key
//   - 块走完弹回稍后处理
// 零错误处理：不检查任何返回值、不防御非预期
#include "simply.h"
#include <windows.h>
#include <stdlib.h>
#include <string.h>

typedef uint32_t u32;

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
static void (*hit(data k))(void) {
    u32 n = k.n;
    for (size_t i = 0; i < PLUGINS_N; i++) {
        size_t ln = strlen(PLUGINS[i].name);
        if (ln == n && memcmp(PLUGINS[i].name, k.d, n) == 0) return PLUGINS[i].run;
    }
    return NULL;
}

/* ================= 全局状态 ================= */
static const uint8_t *ptr;             /* 当前 token 在块数据中的位置（指向 nlen 字段） */
const uint8_t *payload; u32 plen;                /* 当前插件 payload（插件内部读） */
static void (*imp)(void);              /* 当前插件（命中后写 vm.exe 导出的 imp） */

/* 返回点栈：每项 8B = 保存的 ptr；retpoint==栈底即空；块缓冲不释放（零错误处理） */
static void *ret_slots[256]; static void **retpoint = ret_slots;
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
static const uint8_t *getfirstdata(data k) {
    Toks ts = load_toks(k.d, k.n);
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
    if (cur_dirty(k.d, k.n)) {                        /* 该块内存有变动 → 上传 server */
        net_upload(k.d, k.n, buf, sz);
        cur_clean();
    }
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

/* 命中后设插件：payload 从 k 深拷贝到全局；imp 写入 vm.exe 导出的变量 */
static void commit_imp(data k) {
    u32 pl = *(u32*)(k.d + k.n);
    const uint8_t *pay = k.d + k.n + 4;
    free((void*)payload);
    payload = (uint8_t*)malloc(pl);
    memcpy((void*)payload, pay, pl);
    plen = pl;
    *get_vm_imp() = imp;
}

/* ================= 返回点栈 ================= */
/* 把 key 写进返回栈：合成 token [n][d]，栈顶 = 当前块 key（泄漏，零错误处理） */
static void push_key(data k) {
    uint8_t *buf = (uint8_t*)malloc(4 + k.n);
    memcpy(buf, &k.n, 4); memcpy(buf + 4, k.d, k.n);
    *(void**)retpoint = buf;
    retpoint += 8;
}

/* 当前块 key = 读返回栈栈顶（token 从栈顶读出自己在哪个 key）；栈空 = 空 key */
void cur_key_of(const uint8_t **out_d, u32 *out_n) {
    if (retpoint == ret_slots) { *out_d = NULL; *out_n = 0; return; }
    const uint8_t *p = (const uint8_t*)*(void**)(retpoint - 8);
    *out_n = *(u32*)p;
    *out_d = p + 4;
}

/* ================= drill：入口 + 下钻循环（用户结构） ================= */
/* 唯一入口：vm 直接调 drill({0,0}) 引导；插件（boot/cond/handrun）调 drill(目标key) 下钻；
   非插件名 token → 循环内压父块 + push_key + getfirstdata 自动下钻；run_next/reset 接棒 */
void drill(data k) {
    if (!booted) {                                       /* 入口（vm 直接调 drill({0,0})） */
        booted = 1;
        retpoint = ret_slots;
        u32 zero = 0;
        ptr = getfirstdata((data){0, NULL});              /* 空 key → 引导块 */
        k = (data){*(u32*)ptr, ptr + 4};                  /* 第一条 token */
    }
    for (;;) {
        if (imp = hit(k)) break;                         /* hit(k) → imp = 插件，回 vm */
        *(void**)retpoint = (void*)ptr;                   /* *(void**)retpoint = ptr（父块位置） */
        retpoint += 8;                                   /* retpoint += 8 */
        push_key(k);                                    /* 当前块 key 写进栈顶（= 块引用 token） */
        ptr = getfirstdata(k);                           /* ptr = getfirstdata(k)：块的第一个 data */
        k = (data){*(u32*)ptr, ptr + 4};                 /* k = 第一条 token */
    }
    commit_imp(k);                                       /* 命中后设插件 */
}
void run_next(void) {
    data k = (data){*(u32*)ptr, ptr + 4};                   /* 当前 token（ptr 正指向它） */
    ptr = (const uint8_t*)k.d + k.n + 4 + *(u32*)((const uint8_t*)k.d + k.n);
    drill((data){*(u32*)ptr, ptr + 4});                    /* 下一条 token */
}

/* 重跑当前块：从返回栈顶读当前块 key，重新取数据（内存 cur 优先 → 编辑立即响应），进 drill */
void reset(void) {
    const uint8_t *d; u32 n;
    cur_key_of(&d, &n);
    data bk = (data){n, d};
    ptr = getfirstdata(bk);
    drill((data){*(u32*)ptr, ptr + 4});
}
