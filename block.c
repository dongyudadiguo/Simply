// block.c —— 公共执行器（对齐 block.py）：fetch/解析/下钻/动态读
#include "vm.h"
#include <stdlib.h>
#include <string.h>
#include <windows.h>

/* ---------------- 插件动态加载（dll，按 sha256 名，导出 plugin_run） ---------------- */
void *load_plugin(VM *vm, const uint8_t *name, uint32_t nlen) {
    PluginEnt *e = vm->plugins;
    while (e) {
        if (e->nlen == nlen && memcmp(e->name, name, nlen) == 0) return e->run;
        e = e->next;
    }
    /* 插件文件名 = sha256(逻辑名).hexdigest() + ".dll"（对齐 Python load_src） */
    char hex[65]; sha256_hex(name, nlen, hex);
    char path[8 + 64 + 5];
    memcpy(path, PLUGIN_DIR "\\", 8);
    memcpy(path + 8, hex, 64);
    memcpy(path + 8 + 64, ".dll", 5);
    HMODULE lib = LoadLibraryA(path);
    if (!lib) return NULL;                              /* 无插件 → 块引用（下钻） */
    void (*run)(VM*, const uint8_t*, uint32_t) = (void*)GetProcAddress(lib, "plugin_run");
    if (!run) { FreeLibrary(lib); return NULL; }
    e = (PluginEnt*)calloc(1, sizeof(PluginEnt));        /* 缓存 */
    e->name = (uint8_t*)malloc(nlen); memcpy(e->name, name, nlen); e->nlen = nlen;
    e->lib = lib; e->run = run;
    e->next = vm->plugins; vm->plugins = e;
    return run;
}

/* ---------------- token 流解析 ---------------- */
/* 解析 blk（server 原始字节）→ tok 数组（name/payload 指向 blk 内）；返回数量 */
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
Toks load_toks(VM *vm, const uint8_t *key, uint32_t klen) {
    Toks ts = {0};
    size_t n = 0;
    Tok *m = vms_cur_get(vm, key, klen, &n);
    if (m) { ts.tok = m; ts.n = n; ts.cap = n; ts.owned = 0; return ts; }   /* 内存优先：改动立即响应，不释放 */

    /* 兜底：fetch 原始字节并解析（一次性，记录拥有权以便下次释放） */
    uint32_t blen = 0;
    uint8_t *blk = vm->cb_fetch(key, klen, &blen);
    if (!blk) return ts;                                     /* 无块 → 空流 */

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

    /* 普通块：全部 token（tok 数组 malloc + name/payload 指向 blk） */
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

/* find_plugin 动态迭代时，释放上次 fetch 解析的 toks（避免泄漏；内存 cur 的 toks 不动） */
static void free_fetched(Toks *ts, VM *vm) {
    (void)vm;
    if (!ts->owned) { ts->tok = NULL; ts->n = ts->cap = 0; return; }   /* 内存 cur 的 toks：editor 拥有，不释放 */
    if (ts->tok) {
        for (size_t k = 0; k < ts->n; k++) {
            free(ts->tok[k].name);
            if (ts->tok[k].payload) free(ts->tok[k].payload);
        }
        free(ts->tok);
    }
    ts->tok = NULL; ts->n = ts->cap = 0;
}


/* ---------------- 执行核心：尾调用连续执行，不压栈 ---------------- */
static VM _vm;                        /* 全局执行上下文（vm.c 入口 run_block(NULL,...) 用） */
static VM *G = &_vm;                  /* 插件拿到的 vm 指针 */

/* 下钻循环（对齐：token 从空 key（大小为零）开始；
 * 命中插件 → 设 imp（run_imp 随后执行）；否则压返回点 + 取块的第一个 data 作下一 token） */
int find_plugin(VM *vm) {
    for (;;) {
        Toks ts = load_toks(vm, vm->cur_key, vm->cur_key_len);   /* 每次现取（内存改动立即响应） */
        if (vm->cur_i >= ts.n) {                                  /* 当前块 token 走完 */
            free_fetched(&ts, vm);
            if (vm->ret_n) {                                      /* 弹返回点回上层 */
                RetItem *r = &vm->ret[--vm->ret_n];
                if (vm->cur_key) free(vm->cur_key);
                vm->cur_key = r->key; vm->cur_key_len = r->klen; vm->cur_i = r->i;
                continue;
            }
            vm->imp = NULL;                                       /* 全部走完 → 执行链结束 */
            return 0;
        }
        Tok t = ts.tok[vm->cur_i]; vm->cur_i++;                   /* 取当前 token */
        void *run = load_plugin(vm, t.name, t.nlen);              /* 命中插件？ */
        if (run) {                                                /* 命中 → 执行 */
            if (vm->imp_payload_buf) free(vm->imp_payload_buf);   /* payload 深拷贝（exec 期间有效） */
            vm->imp_payload_buf = NULL;
            if (t.plen) {
                vm->imp_payload_buf = (uint8_t*)malloc(t.plen);
                memcpy(vm->imp_payload_buf, t.payload, t.plen);
            }
            vm->imp = run; vm->imp_payload = vm->imp_payload_buf; vm->imp_plen = t.plen;
            free_fetched(&ts, vm);
            return 1;
        }
        /* 块引用 → 压返回点 + 取块的第一个 data（下钻） */
        vm->ret = (RetItem*)realloc(vm->ret, (vm->ret_n + 1) * sizeof(RetItem));
        RetItem *r = &vm->ret[vm->ret_n++];
        r->key = vm->cur_key; r->klen = vm->cur_key_len; r->i = vm->cur_i;
        vm->cur_key = (uint8_t*)malloc(t.nlen); memcpy(vm->cur_key, t.name, t.nlen);
        vm->cur_key_len = t.nlen;
        vm->cur_i = 0;                                            /* data 开头的第一个 token */
        free_fetched(&ts, vm);
    }
}

/* 执行链：尾调用无限连续（-O2 尾调用优化 → jump，函数栈不增长）；
 * 插件内通过回调（run_next/reset/run_block）更新 imp，执行完尾调用继续 */
static void run_imp(void) {
    VM *vm = G;
    if (!vm->imp) return;                                         /* 全部走完 */
    vm->imp(vm, vm->imp_payload, vm->imp_plen);                   /* 执行当前插件 */
    return run_imp();                                             /* 尾调用 → 接棒下一插件 */
}

/* ---------------- 入口 / 下钻 / 接棒 ---------------- */
void run_block(VM *vm, const uint8_t *key, uint32_t klen) {
    if (!vm) {                                                    /* 入口（vm.c: run_block(NULL,NULL,0)） */
        vm = G;
        block_init(vm);                                           /* 首次：设回调表 */
        vm->ret = (RetItem*)malloc(sizeof(RetItem));              /* 分配返回栈（空） */
        vm->ret_n = 0; vm->ret_cap = 1;
        vm->cur_key = NULL; vm->cur_key_len = 0;                  /* 从 token 大小为零开始 */
        vm->cur_i = 0;
        find_plugin(vm);                                          /* 下钻到首个命中插件 */
        run_imp();                                                /* 启动执行链（尾调用） */
        return;
    }
    /* 下钻（插件内回调）：压返回点 + 切块 */
    vm->ret = (RetItem*)realloc(vm->ret, (vm->ret_n + 1) * sizeof(RetItem));
    RetItem *r = &vm->ret[vm->ret_n++];
    r->key = vm->cur_key; r->klen = vm->cur_key_len; r->i = vm->cur_i;
    if (vm->cur_key) free(vm->cur_key);
    vm->cur_key = (uint8_t*)malloc(klen ? klen : 1); memcpy(vm->cur_key, key, klen);
    vm->cur_key_len = klen;
    vm->cur_i = 0;
    find_plugin(vm);                                              /* 更新 imp（当前 run_imp 链继续执行） */
}

void run_next(VM *vm) { find_plugin(vm); }          /* 插件自主接棒：位置已推进，更新 imp */
void reset(VM *vm)   { vm->cur_i = 0; find_plugin(vm); }   /* 重跑当前块 */

/* ---------------- 初始化 ---------------- */
void block_init(VM *vm) {
    vm->cb_run_next = run_next;
    vm->cb_reset = reset;
    vm->cb_run_block = run_block;
    vm->cb_push = vms_push;
    vm->cb_pop = vms_pop;
    vm->cb_write_num = vms_write_num;
    vm->cb_fetch = net_fetch;
    vm->cb_upload = net_upload;
    vm->cb_hand_set = vms_hand_set;
    vm->cb_hand_get = vms_hand_get;
    vm->cb_cur_get = vms_cur_get;
    vm->cb_cur_set = vms_cur_set;
    vm->cb_load_toks = load_toks;
}
