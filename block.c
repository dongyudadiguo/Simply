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
#include <windows.h>                                      /* LoadLibraryA / GetProcAddress / GetModuleHandle */
#include "simply.h"                                       /* data/Tok/Toks/BlockAPI 与 net/sha256/vmstate 声明 */
#include <stdlib.h>                                       /* malloc / calloc / free / rand */
#include <string.h>                                       /* memcpy / strcat */
#include <stdio.h>                                        /* sprintf / fopen / fread / fwrite / fclose */

typedef uint32_t u32;                                     /* 本文件内短名，与 simply.h 的 u32 同义 */

/* hit(token)：token → sha256 → <sha256>.dll 文件名 → LoadLibrary → GetProcAddress("run")
   加载失败 → NULL（= 块引用，下钻）——标准接棒
   零长名（nlen=0）：sha256("") = e3b0c442….dll 已删除 → LoadLibrary 失败 → NULL（块引用，
   下钻空 key 编辑器块）；结尾标记 ENDMK 不是 token */
/* 注意：hit 不特判 nlen==0 —— 零长名不命中 DLL 完全由「该 dll 不存在」自然达成 */
static void (*hit(data k))(void) {                        /* 返回插件 run，失败 NULL */
    uint8_t h[32];                                        /* sha256 摘要缓冲 */
    sha256(k.d, k.n, h);                                  /* token 字节 → 32B 哈希 */
    char fn[70];                                          /* "xxxxxxxx….dll\0"，64 hex + 4 后缀 */
    for (int i = 0; i < 32; i++) sprintf(fn + 2*i, "%02x", h[i]); /* 哈希转小写 hex 文件名前缀 */
    fn[64] = 0;                                           /* 截断保证结尾（sprintf 已写 \0，再钉一次） */
    strcat(fn, ".dll");                                   /* 拼成 <sha256>.dll */
    HMODULE m = LoadLibraryA(fn);                         /* 加载插件 DLL；失败则 m=NULL */
    return (void (*)(void))GetProcAddress(m, "run");      /* 取导出 run；m=NULL 时即 NULL */
}

/* ================= 全局状态 ================= */
const uint8_t *ptr;                   /* 当前 token 在块数据中的位置（指向 nlen 字段，插件从它推自己的 payload） */
static void (*imp)(void);              /* 当前插件（命中后写 vm.exe 导出的 imp） */

/* 返回点栈：字节缓冲（[8B 父块位置][key数据][4B key长度]），retpoint 为游标，retbase 为基址（空栈判断） */
static void *retpoint = NULL; static void *retbase = NULL; /* 游标 / 基址，run 里分配 */

/* ================= 块 token 流（内存 cur 优先 / server 兜底） ================= */
/* 解析 server 原始字节 → tok 数组（name/payload 指向 blk 内）
   结尾标记：nlen == ENDMK（4 字节全 1），不计入 token；须在 i+=nl 之前判定，避免 0xFFFFFFFF 溢出 */
static size_t iter_tokens(const uint8_t *blk, u32 blen, Tok *out, size_t cap) { /* blk[blen] → out[]，返回条数 */
    u32 i = 0; size_t n = 0;                              /* i=字节游标，n=已解析 token 数 */
    while (i + 4 <= blen) {                               /* 至少还能读一个 nlen */
        u32 nl; memcpy(&nl, blk + i, 4);                  /* 读 name 长度 */
        if (nl == ENDMK) break;                           /* 4B 全 1 = 结尾标记（不计入 token） */
        i += 4;                                           /* 推进 4 */
        out[n].name = (uint8_t*)blk + i; out[n].nlen = nl; i += nl; /* name 指向 blk 内，跳过 name 字节 */
        if (i + 4 > blen) break;                           /* 名字后无 plen：截断，停 */
        u32 dl; memcpy(&dl, blk + i, 4); i += 4;          /* 读 payload 长度，推进 4 */
        out[n].payload = (uint8_t*)blk + i; out[n].plen = dl; i += dl; /* payload 指向 blk 内，跳过 payload 字节 */
        n++;                                              /* 计入一条完整 token */
    }
    (void)cap;                                            /* cap 未用（调用方保证 out 够大） */
    return n;                                             /* 完整 token 条数（结尾标记不计） */
}

/* 取块 token 流：内存 cur（editor 实时编辑）优先，否则 fetch server 解析。
   空 key（klen==0）也是普通块（空 key 编辑器块），完整解析全部 token。 */
Toks load_toks(const uint8_t *key, u32 klen) {                   /* key → toks（cur 优先 / server 兜底） */
    Toks ts = {0};                                        /* 返回值清零 */
    size_t n = 0;                                         /* cur_get 写出的 token 数 */
    Tok *m = cur_get(key, klen, &n);                      /* 内存 cur 查表（editor 正在编的块） */
    if (m) { ts.tok = m; ts.n = n; ts.cap = n; ts.owned = 0; return ts; }   /* 内存 cur：editor 拥有，不拷贝不释放 */

    u32 blen = 0;                                         /* server 块字节数 */
    uint8_t *blk = net_fetch(key, klen, &blen);           /* 向 server 取原始块（malloc） */
    /* 非标准/未定义行为：server 无此 key → 自动上传 4 字节全 1（结尾标记=空块），再按空块继续 */
    if (!blk) {                                           /* server 没有这个 key */
        u32 endmk = ENDMK;                                /* 4B 全 1 = 结尾标记 = 空块 */
        net_upload(key, klen, (const uint8_t*)&endmk, 4); /* 占位上传，之后再 fetch 能取到 */
        blk = (uint8_t*)malloc(4);                        /* 本地也造一份空块 */
        memcpy(blk, &endmk, 4);                           /* 填结尾标记 */
        blen = 4;                                         /* 长度 4 */
    }

    Tok tmp[256];                                         /* 栈上暂存解析结果（上限 256） */
    size_t cnt = iter_tokens(blk, blen, tmp, 256);        /* 解析全部 token（name/payload 仍指向 blk） */
    ts.tok = (Tok*)calloc(cnt, sizeof(Tok));              /* 堆上复制，脱离 blk 生命周期 */
    for (size_t k = 0; k < cnt; k++) {                    /* 逐条深拷贝 */
        ts.tok[k].name = (uint8_t*)malloc(tmp[k].nlen);   /* name 缓冲 */
        memcpy(ts.tok[k].name, tmp[k].name, tmp[k].nlen); /* 拷 name */
        ts.tok[k].nlen = tmp[k].nlen;                     /* 名长 */
        ts.tok[k].payload = (uint8_t*)malloc(tmp[k].plen);/* payload 缓冲 */
        memcpy(ts.tok[k].payload, tmp[k].payload, tmp[k].plen); /* 拷 payload */
        ts.tok[k].plen = tmp[k].plen;                     /* payload 长 */
    }
    ts.n = ts.cap = cnt; ts.owned = 1;                    /* 本函数拥有 */
    free(blk);                                            /* 释放 server 原始字节 */
    return ts;                                            /* 深拷贝后的 toks */
}

/* 释放本次 fetch 解析的 toks（内存 cur 的 toks 由 editor 拥有，不动） */
static void free_fetched(Toks *ts) {                            /* owned=1 才释放；cur 的只摘指针 */
    if (!ts->owned) { ts->tok = NULL; ts->n = ts->cap = 0; return; } /* editor 的 cur：只摘指针，不 free */
    for (size_t k = 0; k < ts->n; k++) {                  /* 逐条释放深拷贝 */
        free(ts->tok[k].name);                            /* name */
        free(ts->tok[k].payload);                         /* payload */
    }
    free(ts->tok);                                        /* token 数组本身 */
    ts->tok = NULL; ts->n = ts->cap = 0;                  /* 置空，防再用 */
}

/* getfirstdata(key)：取块的第一个 data（内存 cur 优先 / server），统一序列化为原始字节。
   不关心 editor；非标准/未定义：server 缺 key → load_toks 补空块（仅 ENDMK）→ 返回仅 ENDMK 缓冲，
   调用方据此下钻行为未定义 */
static const uint8_t *getfirstdata(data k) {                    /* 序列化整块，返回缓冲（第一条 token 在开头） */
    Toks ts = load_toks(k.d, k.n);                        /* 取该 key 的全部 token */
    u32 sz = 4;                                        /* 结束符 4B 全 1 */
    for (size_t i = 0; i < ts.n; i++) sz += 4 + ts.tok[i].nlen + 4 + ts.tok[i].plen; /* 累加每条 [nlen][name][plen][payload] */
    uint8_t *buf = (uint8_t*)malloc(sz);                  /* 序列化缓冲（调用方不释放，按文件头约定） */
    u32 off = 0;                                          /* 写游标 */
    for (size_t i = 0; i < ts.n; i++) {                   /* 逐条写出 */
        memcpy(buf + off, &ts.tok[i].nlen, 4); off += 4;  /* nlen */
        memcpy(buf + off, ts.tok[i].name, ts.tok[i].nlen); off += ts.tok[i].nlen; /* name */
        memcpy(buf + off, &ts.tok[i].plen, 4); off += 4;  /* plen */
        memcpy(buf + off, ts.tok[i].payload, ts.tok[i].plen); off += ts.tok[i].plen; /* payload */
    }
    u32 z = ENDMK; memcpy(buf + off, &z, 4);              /* 末尾 4B 全 1 = 结尾标记 */
    if (cur_dirty(k.d, k.n)) {                        /* 该块内存有变动 → 上传 server */
        net_upload(k.d, k.n, buf, sz);                    /* 把刚序列化的字节同步上去 */
        cur_clean();                                      /* 清脏标记 */
    }
    free_fetched(&ts);                                    /* 释放 toks（cur 的不动） */
    return buf;                                           /* ptr 将指向这块缓冲的第一条 token */
}

/* ================= vm imp（GetProcAddress 写 vm 导出的 imp） ================= */
/* 取 vm.exe 导出的 imp 变量地址（缓存） */
static void (**vm_imp)(void) = NULL;                      /* 缓存：指向 vm.exe 导出的 imp 函数指针 */
static void **get_vm_imp(void) {                                /* 返回 vm.exe 导出 imp 的地址 */
    if (!vm_imp) vm_imp = (void (**)(void))GetProcAddress(GetModuleHandle(NULL), "imp"); /* 本进程=vm.exe，取导出 imp */
    return (void**)vm_imp;                                /* 当作 void** 交给赋值方 */
}

/* 命中后设插件：payload 从 k 深拷贝到全局；imp 写入 vm.exe 导出的变量 */

/* 当前插件 payload = 从 ptr 推出（ptr 指向 token 的 nlen 字段） */
void cur_payload(const uint8_t **out_p, u32 *out_n) {           /* 从 ptr 推出当前 token 的 payload */
    *out_n = *(u32*)(ptr + 4 + *(u32*)ptr);               /* 跳过 [nlen][name] 读 plen */
    *out_p = ptr + 4 + *(u32*)ptr + 4;                    /* 再跳 plen 字段，指向 payload 字节 */
}

/* ================= 返回点栈 ================= */
/* 压 [8B 父块位置][key=当前 token 名][4B key长度]，栈顶（末尾）= 当前块 key；和 pop_ret 成对 */
static void push_ret(void) {                                  /* 压 [父ptr 8B][key=当前 token][len 4B] */
    *(void**)retpoint = (void*)ptr;                           /* 8B：父块位置（当前 token 位置，弹回用） */
    retpoint += 8;                                            /* 推进 8 */
    u32 n = *(u32*)ptr;                                       /* key 长 = 当前 token 名长 */
    memcpy(retpoint, ptr + 4, n);                             /* key 数据 = 当前 token 名 */
    retpoint += n;                                            /* 推进 key 长 */
    *(u32*)retpoint = n;                                      /* 4B：key 长度（倒读栈顶用） */
    retpoint += 4;                                            /* 推进 4，栈顶落在该项末尾 */
}

static void push_key(data k) {                                  /* 压 [父ptr 8B][key][len 4B] */
    *(void**)retpoint = (void*)ptr;                   /* 8B：父块位置（当前 token 位置，弹回用） */
    retpoint += 8;                                        /* 推进 8 */
    memcpy(retpoint, k.d, k.n);                       /* key 数据（变长） */
    retpoint += k.n;                                      /* 推进 key 长 */
    *(u32*)retpoint = k.n;                            /* 4B：key 长度（倒读栈顶用） */
    retpoint += 4;                                        /* 推进 4，栈顶落在该项末尾 */
}

/* 当前块 key = 读返回栈末尾（[key数据][4B key长度]）；栈空 = 空 key */
void cur_key_of(const uint8_t **out_d, u32 *out_n) {            /* 读栈顶当前块 key */
    if (retpoint == retbase) { *out_d = NULL; *out_n = 0; return; } /* 空栈：空 key */
    u32 n = *(u32*)((const uint8_t*)retpoint - 4);        /* 倒读 4B = 栈顶项 key 长 */
    *out_n = n;                                           /* 写出长度 */
    *out_d = (const uint8_t*)retpoint - 4 - n;            /* 再倒 n 字节 = key 数据起点 */
}

/* 弹回：块结束 → 恢复父块 ptr（父块的块引用 token 位置），并弹掉该项 */
static void pop_ret(void) {                                     /* 弹栈顶，ptr 回到父块引用 token */
    u32 n = *(u32*)((const uint8_t*)retpoint - 4);                 /* 最后一项 key 长度 */
    const uint8_t *start = (const uint8_t*)retpoint - 4 - n - 8;    /* 该项起点（[8B父ptr][key][4B len]） */
    ptr = *(const void**)start;                                    /* 恢复父块 ptr */
    retpoint = (void*)start;                                       /* 弹掉该项 */
}

/* ================= drill：下钻循环（用户结构） ================= */
/* 插件（cond/handrun）调 drill(目标key) 下钻；run_next/reset 接棒；
   非插件名 token → 循环内 push_key(k) + getfirstdata 自动下钻（k 不必在 ptr 上，故可 drill(id)） */
void drill(data k) {                                            /* 下钻直到 hit 插件，写 vm.imp */
    for (;;) {                                            /* 一直下钻直到命中插件 */
        if (imp = hit(k)) break;                         /* hit(k) → imp = 插件，回 vm */
        push_key(k);                                      /* 非插件 = 块引用：压父位置 + k 作 key（不读 ptr） */
        ptr = getfirstdata(k);                           /* ptr = getfirstdata(k)：块的第一个 data */
        /* 非标准/未定义：空块（仅 ENDMK）→ k.n = ENDMK、k.d 越界，后续下钻未定义（getfirstdata 不关心 editor） */
        k = (data){*(u32*)ptr, ptr + 4};            /* k = 第一条 token */
    }
    *get_vm_imp() = imp;                                 /* 命中后写 vm 的 imp；payload 插件自己从 ptr 推 */
}

/* ================= run：vm 专用入口 ================= */
/* vm 调一次：初始化返回栈 + 读/建 id.bin，drill(id)。插件不调。 */
void run(void) {                                          /* vm 专用：建栈 + 引导 id + drill(id) */
    retbase = malloc(256 * sizeof(void*));                /* 返回栈缓冲（按指针槽估大小） */
    retpoint = retbase;                                   /* 空栈：游标=基址 */
    uint8_t id[32];                                       /* 32B 块 key */
    FILE *f = fopen("id.bin", "rb");                      /* 本地持久化的根块 id */
    if (f) {                                              /* 文件在 → 直接用，不查 server、不检查读长 */
        fread(id, 1, 32, f);                              /* 读 32B id */
        fclose(f);                                        /* 关文件 */
    } else {                                              /* 无 id.bin → 新建随机 id，上传零 data + 结尾标记（12B） */
        for (int i = 0; i < 32; i++) id[i] = (uint8_t)(rand() & 0xff);   /* 新 id */
        f = fopen("id.bin", "wb"); fwrite(id, 1, 32, f); fclose(f); /* 写回本地 */
        uint8_t block[12] = {0,0,0,0, 0,0,0,0, 0xFF,0xFF,0xFF,0xFF}; /* 零长名 token（下钻空 key 编辑器块）+ 结尾标记 0xFF×4 */
        net_upload(id, 32, block, 12);                    /* 上传空根块：[0][ ][0][ ] + 4B 全 1 尾 */
    }
    drill((data){32, id});                                /* 直接下钻 id：hit 失败 → push_key(id) → getfirstdata(id) */
}
void run_next(void) {                                           /* 跳过当前 token，drill 下一条（遇尾则弹回） */
    ptr += 4 + *(u32*)ptr;                                /* 跳过当前 token 的 [nlen][name] */
    ptr += 4 + *(u32*)ptr;                                /* 再跳 [plen][payload]，落到下一条 nlen */
    /* 非标准/未定义行为：下一条为结尾标记 ENDMK → 块返回（弹父块继续下一条）；根块则 drill 零长名 → 空 key 编辑器块 */
    while (*(u32*)ptr == ENDMK) {                         /* 连续结尾标记都弹 */
        if (retpoint == retbase) {
            /* 非标准/未定义/约定：根块结束 → 零长名 → 下钻空 key 编辑器块（编辑循环边界），不是标准块逻辑 */
            drill((data){0, ptr});                        /* 零长名 → hit 失败 → 空 key 块 */
            return;                                       /* 编辑器块接棒，不再往下 */
        }
        pop_ret();                                         /* 非标准/未定义：恢复父块 ptr（块引用 token 位置） */
        ptr += 4 + *(u32*)ptr;                             /* 跳过父块的块引用 token */
        ptr += 4 + *(u32*)ptr;                            /* 再跳它的 payload，落到父块下一条 */
    }
    drill((data){*(u32*)ptr, ptr + 4});                    /* 下一条 token（标准接棒） */
}

/* 重跑当前块：从返回栈顶读当前块 key，重新取数据（内存 cur 优先 → 编辑立即响应），进 drill */
void reset(void) {                                              /* 按栈顶 key 重取块，从第一条再 drill */
    const uint8_t *d; u32 n;                              /* 当前块 key 的指针/长度 */
    cur_key_of(&d, &n);                                   /* 从栈顶读 */
    data bk = (data){n, d};                               /* 合成 data */
    ptr = getfirstdata(bk);                               /* 重新取块（cur 优先，编辑立刻可见） */
    /* 非标准/未定义：空块（仅 ENDMK）→ 零长名下钻（与 drill 空块情形相同，getfirstdata 不关心 editor） */
    if (*(u32*)ptr == ENDMK) drill((data){0, ptr});
    else drill((data){*(u32*)ptr, ptr + 4});              /* 从第一条重新钻 */
}


/* 取块全部 token 名（补全用）：不解析 payload，只收集名字 */
void load_names(const uint8_t *key, u32 klen, uint8_t (*names)[64], u32 *out_n, u32 maxn) { /* 只收 token 名，补全用 */
    u32 blen = 0;                                         /* server 块长 */
    uint8_t *blk = net_fetch(key, klen, &blen);           /* 直接 fetch，不走 cur */
    if (!blk) { *out_n = 0; return; }                     /* 没有就空列表 */
    u32 i = 0, n = 0;                                     /* i=字节游标，n=已收名字数 */
    while (i + 4 <= blen && n < maxn) {                   /* 还能读 nlen 且没满 */
        u32 nl; memcpy(&nl, blk + i, 4);                  /* 读名长 */
        if (nl == ENDMK) break;                           /* 4B 全 1 = 结尾标记 */
        i += 4;                                           /* 推进 4 */
        u32 c = nl < 64 ? nl : 64;                        /* 截断进 64B 槽（含 \0 位置） */
        memcpy(names[n], blk + i, c); names[n][c] = 0; n++; /* 拷名字并 \0 终止 */
        i += nl;                                          /* 跳过 name 原长（不是截断长） */
        if (i + 4 > blen) break;                          /* 没有 plen 就停 */
        u32 dl; memcpy(&dl, blk + i, 4); i += 4 + dl;     /* 读 plen 并跳过 payload，不收内容 */
    }
    free(blk);                                            /* 释放 fetch 缓冲 */
    *out_n = n;                                           /* 写出名字条数 */
}
static int net_upload_fn(const uint8_t *key, u32 klen, const uint8_t *data, u32 dlen) { /* BlockAPI 函数指针包装 */
    return net_upload(key, klen, data, dlen);             /* 函数指针包装，塞进 BlockAPI */
}

/* ================= 显式动态链接接口 ================= */
/* 插件 DLL 运行时 GetProcAddress("block_api") 取函数/全局表（不再 -lblock 隐式链接） */
BlockAPI block_api_st = {                                 /* 全局表：插件经 block_import() 拿到 */
    stk, &stk_off, num, &num_off, var, &var_off,          /* vmstate 三个区 + 各自游标 */
    push, write_num, cur_set, cur_get, hand_set, hand_get, /* 栈/内存块/handrun */
    run_next, reset, drill, cur_payload, cur_key_of, load_toks, /* 执行接棒 + 当前 token/块 */
    load_names, net_upload_fn,                            /* 补全名表 + 上传（拖出占位） */
    heat_add, heat_get,                                   /* 热力计数 */
    GET, SET                                              /* 全局变量（GET/SET token） */
};
BlockAPI *block_api(void) { return &block_api_st; }       /* block.dll 导出：插件 GetProcAddress 入口 */
