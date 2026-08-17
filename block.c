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
//   - 块走完弹回 / server 无 key 补空块：均为非标准/未定义行为（见下方标注）
// 零错误处理：不检查任何返回值、不防御非预期
#include <windows.h>
#include "simply.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

typedef uint32_t u32;

/* hit(token)：token → sha256 → <sha256>.dll 文件名 → LoadLibrary → GetProcAddress("run")
   加载失败 → NULL（= 块引用，下钻）——标准接棒
   非标准/未定义行为：零大小 data（nlen=0 / 结尾标记）→ sha256("") = e3b0c442….dll（editor） */
static void (*hit(data k))(void) {
    uint8_t h[32];
    sha256(k.d, k.n, h);
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
/* 解析 server 原始字节 → tok 数组（name/payload 指向 blk 内）
   非标准/未定义行为：0 长 name / 名字后无 plen = 结尾标记（不计入 token） */
static size_t iter_tokens(const uint8_t *blk, u32 blen, Tok *out, size_t cap) {
    u32 i = 0; size_t n = 0;
    while (i + 4 <= blen) {
        u32 nl; memcpy(&nl, blk + i, 4); i += 4;
        out[n].name = (uint8_t*)blk + i; out[n].nlen = nl; i += nl;
        if (i + 4 > blen) break;                           /* 非标准/未定义：名字后无 plen = 结尾标记 */
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
    /* 非标准/未定义行为：server 无此 key → 自动上传 4 字节全零（结尾标记=空块），再按空块继续 */
    if (!blk) {
        static const uint8_t endmk[4] = {0, 0, 0, 0};
        net_upload(key, klen, endmk, 4);
        blk = (uint8_t*)malloc(4);
        memcpy(blk, endmk, 4);
        blen = 4;
    }

    if (klen == 0) {                                         /* 引导：空 key 只取第一条 name */
        Tok tmp[1] = {0};
        size_t cnt = iter_tokens(blk, blen, tmp, 1);
        ts.tok = (Tok*)calloc(1, sizeof(Tok));
        ts.n = ts.cap = 1; ts.owned = 1;
        /* 非标准/未定义：空块（仅结尾标记）→ 零长名 = editor */
        u32 nl = cnt ? tmp[0].nlen : 0;
        ts.tok[0].name = (uint8_t*)malloc(nl ? nl : 1);
        if (nl) memcpy(ts.tok[0].name, tmp[0].name, nl);
        ts.tok[0].nlen = nl;
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

/* 弹回：块结束 → 恢复父块 ptr（父块的块引用 token 位置），并弹掉该项 */
static void pop_ret(void) {
    u32 n = *(u32*)((const uint8_t*)retpoint - 4);                 /* 最后一项 key 长度 */
    const uint8_t *start = (const uint8_t*)retpoint - 4 - n - 8;    /* 该项起点（[8B父ptr][key][4B len]） */
    ptr = *(const void**)start;                                    /* 恢复父块 ptr */
    retpoint = (void*)start;                                       /* 弹掉该项 */
}

/* ================= drill：入口 + 下钻循环（用户结构） ================= */
/* 唯一入口：vm 直接调 drill({0,0}) 引导；插件（boot/cond/handrun）调 drill(目标key) 下钻；
   非插件名 token → 循环内压父块 + push_key + getfirstdata 自动下钻；run_next/reset 接棒 */
void drill(data k) {
    if (!booted) {                                       /* 入口（vm 直接调 drill({0,0})）—— 引导逻辑集成在此（原 boot 插件） */
        booted = 1;
        retbase = malloc(256 * sizeof(void*));
        retpoint = retbase;
        /* 非标准/未定义：无 id / server 无该 id → 新建随机 id，上传零 data + 结尾标记（12B） */
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
            uint8_t block[12] = {0,0,0,0, 0,0,0,0, 0,0,0,0};   /* 非标准/未定义：零 data（editor）+ 结尾标记 */
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
    /* 非标准/未定义行为：下一条为结尾标记（零长名）→ 块返回（弹父块继续下一条）；根块则 drill 该零长名 → editor */
    while (*(u32*)ptr == 0) {
        if (retpoint == retbase) {                          /* 非标准/未定义：根块结束 → editor */
            drill((data){*(u32*)ptr, ptr + 4});
            return;
        }
        pop_ret();                                         /* 非标准/未定义：恢复父块 ptr（块引用 token 位置） */
        ptr += 4 + *(u32*)ptr;                             /* 跳过父块的块引用 token */
        ptr += 4 + *(u32*)ptr;
    }
    drill((data){*(u32*)ptr, ptr + 4});                    /* 下一条 token（标准接棒） */
}

/* 重跑当前块：从返回栈顶读当前块 key，重新取数据（内存 cur 优先 → 编辑立即响应），进 drill */
void reset(void) {
    const uint8_t *d; u32 n;
    cur_key_of(&d, &n);
    data bk = (data){n, d};
    ptr = getfirstdata(bk);
    drill((data){*(u32*)ptr, ptr + 4});
}


/* 取块全部 token 名（补全用）：不解析 payload，只收集名字 */
void load_names(const uint8_t *key, u32 klen, uint8_t (*names)[64], u32 *out_n, u32 maxn) {
    u32 blen = 0;
    uint8_t *blk = net_fetch(key, klen, &blen);
    if (!blk) { *out_n = 0; return; }
    u32 i = 0, n = 0;
    while (i + 4 <= blen && n < maxn) {
        u32 nl; memcpy(&nl, blk + i, 4); i += 4;
        if (!nl) break;                          /* 非标准/未定义：零长名 = 结尾标记 */
        u32 c = nl < 64 ? nl : 64;
        memcpy(names[n], blk + i, c); names[n][c] = 0; n++;
        i += nl;
        if (i + 4 > blen) break;
        u32 dl; memcpy(&dl, blk + i, 4); i += 4 + dl;
    }
    free(blk);
    *out_n = n;
}
static int net_upload_fn(const uint8_t *key, u32 klen, const uint8_t *data, u32 dlen) {
    return net_upload(key, klen, data, dlen);
}

/* ================= 显式动态链接接口 ================= */
/* 插件 DLL 运行时 GetProcAddress("block_api") 取函数/全局表（不再 -lblock 隐式链接） */
BlockAPI block_api_st = {
    stk, &stk_off, num, &num_off, var, &var_off,
    push, write_num, cur_set, cur_get, hand_set, hand_get,
    run_next, reset, drill, cur_payload, cur_key_of, load_toks,
    load_names, net_upload_fn,
    heat_add, heat_get
};
BlockAPI *block_api(void) { return &block_api_st; }
