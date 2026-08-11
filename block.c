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
//   - 命中后：imp 写入 vm.exe 导出的变量；插件 payload 从 ptr 推出
//   - 块数据按需取（内存 cur 优先 / server），缓冲不释放
//   - 当前块 key 写进返回栈（每个下钻压 [父块位置, key合成token]），栈顶 = 当前块 key
//   - 块走完弹回稍后处理
// 零错误处理：不检查任何返回值、不防御非预期
#include "simply.h"
#include <windows.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

typedef uint32_t u32;

/* hit(token)：token → sha256 → <sha256>.dll 文件名 → LoadLibrary → GetProcAddress("run")
   零大小 data = editor（按 "editor" 哈希）；加载失败 → NULL（= 块引用，下钻） */
static void (*hit(data k))(void) {
    const uint8_t *name = k.d; u32 nlen = k.n;
    uint8_t zero_editor[6];
    if (!nlen) { memcpy(zero_editor, "editor", 6); name = zero_editor; nlen = 6; }   /* 零大小 data = editor */
    uint8_t h[32];
    sha256(name, nlen, h);
    char fn[70];
    for (int i = 0; i < 32; i++) sprintf(fn + 2*i, "%02x", h[i]);
    fn[64] = 0;
    strcat(fn, ".dll");
    HMODULE m = LoadLibraryA(fn);
    return (void (*)(void))GetProcAddress(m, "run");
}

/* ================= 全局状态 ================= */
const uint8_t *ptr;                   /* 当前 token 在块数据中的位置（指向 nlen 字段，插件从它推自己的 payload） */
static void (*imp)(void);              /* 当前插件（命中后写 vm.exe 导出的 imp） */

/* 返回点栈：字节缓冲（[8B 父块位置][key数据][4B key长度]），retpoint 为游标，retbase 为基址（空栈判断） */
static void *retpoint = NULL; static void *retbase = NULL;
static int booted = 0;                 /* 入口是否已初始化 */

/* ================= 块 token 流（内存 cur 优先 / server 兜底） ================= */
/* 解析 server 原始字节 → tok 数组（name/payload 指向 blk 内）；0 长 name = 块结束 */
static size_t iter_tokens(const uint8_t *blk, u32 blen, Tok *out, size_t cap) {
    u32 i = 0; size_t n = 0;
    while (i + 4 <= blen) {
        u32 nl; memcpy(&nl, blk + i, 4); i += 4;
        out[n].name = (uint8_t*)blk + i; out[n].nlen = nl; i += nl;
        if (i + 4 > blen) break;                           /* 名字后无 plen 字段 = 尾标记 */
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

/* 当前插件 payload = 从 ptr 推出（ptr 指向 token 的 nlen 字段） */
void cur_payload(const uint8_t **out_p, u32 *out_n) {
    *out_n = *(u32*)(ptr + 4 + *(u32*)ptr);
    *out_p = ptr + 4 + *(u32*)ptr + 4;
}

/* ================= 返回点栈 ================= */
/* 把 key 写进返回栈：[8B 父块位置][key数据][4B key长度]，栈顶（末尾）= 当前块 key */
static void push_key(data k) {
    *(void**)retpoint = (void*)ptr;                   /* 8B：父块位置 */
    retpoint += 8;
    memcpy(retpoint, k.d, k.n);                       /* key 数据 */
    retpoint += k.n;
    *(u32*)retpoint = k.n;                            /* 4B：key 长度 */
    retpoint += 4;
}

/* 当前块 key = 读返回栈末尾（[key数据][4B key长度]）；栈空 = 空 key */
void cur_key_of(const uint8_t **out_d, u32 *out_n) {
    if (retpoint == retbase) { *out_d = NULL; *out_n = 0; return; }
    u32 n = *(u32*)((const uint8_t*)retpoint - 4);
    *out_n = n;
    *out_d = (const uint8_t*)retpoint - 4 - n;
}

/* ================= drill：入口 + 下钻循环（用户结构） ================= */
/* 唯一入口：vm 直接调 drill({0,0}) 引导；插件（boot/cond/handrun）调 drill(目标key) 下钻；
   非插件名 token → 循环内压父块 + push_key + getfirstdata 自动下钻；run_next/reset 接棒 */
void drill(data k) {
    if (!booted) {                                       /* 入口（vm 直接调 drill({0,0})）—— 引导逻辑集成在此（原 boot 插件） */
        booted = 1;
        retbase = malloc(256 * sizeof(void*));
        retpoint = retbase;
        /* 有 id 运行 id；没有新建随机 id 并上传零 data + 尾标记（4+4+4=12B）到 id */
        uint8_t id[32];
        FILE *f = fopen("id.bin", "rb");
        int fresh = 1;
        if (f) {
            if (fread(id, 1, 32, f) == 32) {
                u32 blen = 0;
                uint8_t *blk = net_fetch(id, 32, &blen);
                if (blk) { free(blk); fresh = 0; }       /* server 有该块 → 直接用 */
            }
            fclose(f);
        }
        if (fresh) {
            for (int i = 0; i < 32; i++) id[i] = (uint8_t)(rand() & 0xff);   /* 新 id */
            f = fopen("id.bin", "wb"); fwrite(id, 1, 32, f); fclose(f);
            uint8_t block[12] = {0,0,0,0, 0,0,0,0, 0,0,0,0};   /* 零 data + 尾标记 */
            net_upload(id, 32, block, 12);
        }
        data idd = {32, id};
        ptr = getfirstdata(idd);                          /* 进 id 块 */
        push_key(idd);                                    /* 压 id key（reset/cur_key_of 用） */
        k = (data){*(u32*)ptr, ptr + 4};                  /* 第一条 token */
    }
    for (;;) {
        if (imp = hit(k)) break;                         /* hit(k) → imp = 插件，回 vm */
        push_key(k);
        ptr = getfirstdata(k);                           /* ptr = getfirstdata(k)：块的第一个 data */
        k = (data){*(u32*)ptr, ptr + 4};                 /* k = 第一条 token */
    }
    *get_vm_imp() = imp;                                 /* 命中后写 vm 的 imp；payload 插件自己从 ptr 推 */
}
void run_next(void) {
    ptr += 4 + *(u32*)ptr;
    ptr += 4 + *(u32*)ptr;
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
