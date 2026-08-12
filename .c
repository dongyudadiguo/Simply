// .c —— 图形编辑器插件（raylib，transition/Python-editor 风格）
// 布局：read 左贴、set 右贴、普通 token 独占一行；payload 显示；颜色区分；指针吸附行间隙
// 交互：中键平移+滚轮缩放(鼠标锚点)、空格插入、Alt/Ctrl 组合插入(松开判定)、SHIFT划选/INSERT粘贴/DELETE划删
//      右键拖出块引用子视图、左键拖动、右键点节点头关闭、handrun 双按钮、补全跟随鼠标
#include <stdint.h>
#include <stddef.h>

typedef uint32_t u32;
typedef struct { uint8_t *name; uint32_t nlen; uint8_t *payload; uint32_t plen; } Tok;
typedef struct { Tok *tok; size_t n, cap, owned; } Toks;
typedef struct { u32 n; const uint8_t *d; } data;
typedef struct {
    uint8_t *stk; uint32_t *stk_off;
    uint8_t *num; uint32_t *num_off;
    uint8_t *var; uint32_t *var_off;
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
    void (*load_names)(const uint8_t*, u32, uint8_t (*)[64], u32*, u32);
    int (*net_upload_fn)(const uint8_t*, u32, const uint8_t*, u32);
} BlockAPI;
extern void *GetModuleHandleA(const char *name);
extern void *GetProcAddress(void *module, const char *name);
static inline BlockAPI *block_import(void) {
    typedef BlockAPI *(*fn)(void);
    return ((fn)GetProcAddress(GetModuleHandleA("block.dll"), "block_api"))();
}
#include "raylib.h"
#include "raymath.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

/* windows API 手动声明（插件不 include windows.h，保持自包含） */
extern unsigned int __stdcall GetFileAttributesA(const char *name);
extern unsigned int __stdcall GetTickCount(void);
#define INVALID_FILE_ATTRIBUTES 0xFFFFFFFF

/* ================= 内嵌 sha256（判定 token 是否命中插件 DLL） ================= */
#define ROTR(x,n) (((x)>>(n))|((x)<<(32-(n))))
#define SHR(x,n) ((x)>>(n))
#define CH(x,y,z) (((x)&(y))^((~(x))&(z)))
#define MAJ(x,y,z) (((x)&(y))^((x)&(z))^((y)&(z)))
#define SIG0(x) (ROTR(x,2)^ROTR(x,13)^ROTR(x,22))
#define SIG1(x) (ROTR(x,6)^ROTR(x,11)^ROTR(x,25))
#define sig0(x) (ROTR(x,7)^ROTR(x,18)^SHR(x,3))
#define sig1(x) (ROTR(x,17)^ROTR(x,19)^SHR(x,10))
static const uint32_t K[64] = {
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
};
static void sha256(const uint8_t *d, uint32_t len, uint8_t out[32]) {
    uint32_t h[8] = {0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,
                     0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
    uint64_t bitlen = (uint64_t)len * 8;
    uint8_t msg[128]; uint32_t mlen = 0;
    for (uint32_t i = 0; i < len; i++) msg[mlen++] = d[i];
    msg[mlen++] = 0x80;
    while ((mlen % 64) != 56) msg[mlen++] = 0;
    for (int i = 7; i >= 0; i--) msg[mlen++] = (uint8_t)(bitlen >> (i * 8));
    for (uint32_t off = 0; off < mlen; off += 64) {
        uint32_t w[64];
        for (int i = 0; i < 16; i++)
            w[i] = ((uint32_t)msg[off+i*4]<<24)|((uint32_t)msg[off+i*4+1]<<16)|
                   ((uint32_t)msg[off+i*4+2]<<8)|(uint32_t)msg[off+i*4+3];
        for (int i = 16; i < 64; i++) w[i] = sig1(w[i-2]) + w[i-7] + sig0(w[i-15]) + w[i-16];
        uint32_t a=h[0],b=h[1],c=h[2],d=h[3],e=h[4],f=h[5],g=h[6],hh=h[7];
        for (int i = 0; i < 64; i++) {
            uint32_t t1 = hh + SIG1(e) + CH(e,f,g) + K[i] + w[i];
            uint32_t t2 = SIG0(a) + MAJ(a,b,c);
            hh=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
        }
        h[0]+=a; h[1]+=b; h[2]+=c; h[3]+=d; h[4]+=e; h[5]+=f; h[6]+=g; h[7]+=hh;
    }
    for (int i = 0; i < 8; i++) {
        out[i*4]   = (uint8_t)(h[i] >> 24);
        out[i*4+1] = (uint8_t)(h[i] >> 16);
        out[i*4+2] = (uint8_t)(h[i] >> 8);
        out[i*4+3] = (uint8_t)h[i];
    }
}

/* ================= CRC32（节点头短名，对齐 Python editor crc_name） ================= */
static uint32_t crc32(const uint8_t *d, size_t len) {
    uint32_t c = 0xFFFFFFFF;
    for (size_t i = 0; i < len; i++) {
        c ^= d[i];
        for (int k = 0; k < 8; k++) c = (c >> 1) ^ (0xEDB88320 & -(c & 1));
    }
    return c ^ 0xFFFFFFFF;
}
static void crc_name(const uint8_t *key, u32 klen, char *out) {
    uint32_t n = crc32(key, klen);
    if (!n) n = 1;
    char rev[16]; int i = 0;
    while (n) { rev[i++] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"[n % 32]; n /= 32; }
    int j = 0; while (i) out[j++] = rev[--i];
    out[j] = 0;
}

/* ================= 插件名列表（补全来源之一，与 upload_boot 一致） ================= */
static const char *PLUGINS[] = {
    "boot","editor","rerun","add","read","set","cond","handrun","condrerun",
    "push_int","in-int","out","rand","gt","lt","eq","mul","ret_int"
};
#define PLUGIN_N (sizeof(PLUGINS)/sizeof(PLUGINS[0]))

/* ================= 常量（对齐 Python editor） ================= */
#define RH 30.0f          /* 行高 */
#define GAP 8.0f          /* 行距 */
#define MAX_VIEW 64
#define MAX_LINE 512
#define MAX_ITEM 1024
static const Color C_BG    = {15, 18, 24, 255};
static const Color C_DIM   = {70, 80, 90, 255};      /* 未命中插件=灰 */
static const Color C_HIT   = {90, 160, 220, 255};    /* 命中插件=蓝 */
static const Color C_GREEN = {98, 201, 130, 255};    /* read */
static const Color C_YELLOW= {232, 200, 120, 255};   /* set */
static const Color C_COND  = {208, 128, 224, 255};   /* cond */
static const Color C_HAND  = {247, 118, 142, 255};   /* handrun */
static const Color C_CRUN  = {255, 158, 100, 255};   /* condrerun */
static const Color C_HEAD  = {120, 130, 145, 255};   /* 节点头 */
static const Color C_PTR   = {200, 200, 200, 255};   /* 指针 */
static const Color C_INP   = {232, 236, 239, 255};   /* 输入 */
static const Color C_LINE  = {0, 255, 0, 255};       /* LIME 连线 */

/* ================= 视图 ================= */
typedef struct {
    uint8_t key[256]; u32 klen;
    Vector2 pos;                 /* 节点头左上角（世界） */
    int src_v; int src_i;        /* 来源（父视图/token，子视图连线用；-1=主） */
    float end_y;
} View;
static View views[MAX_VIEW];
static int view_n = 0;

/* 行布局：read 左贴、set 右贴、普通独占一行 */
typedef struct { int kind; int idx; float x; float w; } Item;  /* kind:0=left 1=name 2=right */
typedef struct { Item items[32]; int n; float width; } Line;
static Line lines[MAX_LINE]; static int line_n = 0;
static Vector2 anchor[MAX_VIEW][512]; static int anchor_n[MAX_VIEW];  /* 每视图每 token 锚点 */

/* 当前编辑目标视图（鼠标所在） */
static int cur_v = 0;

/* ================= token 名字/属性判定 ================= */
static int name_is(const Tok *t, const char *s) {
    size_t n = strlen(s);
    return t->nlen == n && memcmp(t->name, s, n) == 0;
}
static int has_plugin(const uint8_t *name, u32 n) {
    if (n == 0) return 1;                       /* 零 data = editor 自身（dll 存在） */
    uint8_t h[32]; sha256(name, n, h);
    char fn[70];
    for (int i = 0; i < 32; i++) sprintf(fn + 2*i, "%02x", h[i]);
    strcat(fn, ".dll");
    return GetFileAttributesA(fn) != INVALID_FILE_ATTRIBUTES;
}

/* 显示文本：read/set/cond/condrerun 有 payload 只显 payload；handrun 显目标；否则名字 */
static void item_label(const Tok *t, char *out) {
    if (t->nlen == 0) { strcpy(out, "(editor)"); return; }
    if (name_is(t, "handrun")) {
        u32 pl = t->plen > 8 ? t->plen - 8 : 0;
        u32 c = pl < 100 ? pl : 100;
        memcpy(out, t->payload + 8, c); out[c] = 0;
        return;
    }
    if ((name_is(t,"read")||name_is(t,"set")||name_is(t,"cond")||name_is(t,"condrerun")) && t->plen > 0) {
        u32 c = t->plen < 100 ? t->plen : 100;
        memcpy(out, t->payload, c); out[c] = 0;
        return;
    }
    u32 c = t->nlen < 100 ? t->nlen : 100;
    memcpy(out, t->name, c); out[c] = 0;
}
static float item_w(const Tok *t) {
    char lb[128]; item_label(t, lb);
    float w = MeasureText(lb, 20) + 20;
    if (name_is(t, "handrun")) w += 26;         /* handrun 双按钮宽 */
    return w;
}
static Color item_color(const Tok *t) {
    if (name_is(t,"read")) return C_GREEN;
    if (name_is(t,"set")) return C_YELLOW;
    if (name_is(t,"cond")) return C_COND;
    if (name_is(t,"handrun")) return C_HAND;
    if (name_is(t,"condrerun")) return C_CRUN;
    if (t->nlen == 0) return C_HIT;             /* editor 自身 */
    return has_plugin(t->name, t->nlen) ? C_HIT : C_DIM;
}

/* ================= 行布局构建 ================= */
static void build_lines(Tok *toks, size_t n) {
    line_n = 0; int left[32]; int left_n = 0;
    for (size_t i = 0; i < n; i++) {
        if (name_is(&toks[i], "read")) { if (left_n < 32) left[left_n++] = (int)i; }
        else if (name_is(&toks[i], "set")) {
            if (line_n > 0) { Line *L = &lines[line_n-1]; if (L->n < 32) L->items[L->n++] = (Item){2, (int)i, 0, item_w(&toks[i])}; }
            else if (left_n < 32) left[left_n++] = (int)i;
        }
        else {
            if (line_n >= MAX_LINE) break;
            Line *L = &lines[line_n++];
            L->n = 0; L->width = 0;
            for (int k = 0; k < left_n; k++) {
                L->items[L->n++] = (Item){0, left[k], 0, item_w(&toks[left[k]])};
                L->width += L->items[L->n-1].w + 6;
            }
            left_n = 0;
            L->items[L->n++] = (Item){1, (int)i, 0, item_w(&toks[i])};
            L->width += L->items[L->n-1].w + 6;
        }
    }
    if (left_n > 0 && line_n < MAX_LINE) {       /* 结尾残留 read */
        Line *L = &lines[line_n++]; L->n = 0; L->width = 0;
        for (int k = 0; k < left_n; k++) {
            L->items[L->n++] = (Item){0, left[k], 0, item_w(&toks[left[k]])};
            L->width += L->items[L->n-1].w + 6;
        }
    }
    /* 行内 x 偏移 */
    for (int r = 0; r < line_n; r++) {
        float x = 0;
        for (int k = 0; k < lines[r].n; k++) { lines[r].items[k].x = x; x += lines[r].items[k].w + 6; }
    }
}

/* ================= 视图坐标 ================= */
/* 视图节点头顶部 = v->pos.y；内容行 row 中心 y = pos.y + RH + row*(RH+GAP) + RH/2 */
static float row_y(const View *v, int row) { return v->pos.y + RH + row*(RH+GAP) + RH/2; }
/* 间隙 j（0..line_n）：j=0 节点头与行0 间；j=i(1..n) 行 i-1 与 i 间；j=n 末尾 */
static float gap_y(const View *v, int j) {
    if (j <= 0) return v->pos.y + RH + GAP/2;
    return v->pos.y + RH + j*(RH+GAP) - GAP/2;
}
/* 鼠标 world → 最近间隙 → 行号 */
static int nearest_gap(const View *v, float wy, int maxj) {
    int best = 0; float bd = 1e9f;
    for (int j = 0; j <= maxj; j++) {
        float d = gap_y(v, j) - wy; if (d < 0) d = -d;
        if (d < bd) { bd = d; best = j; }
    }
    return best;
}
/* 行 j 的起始 token 索引（插入位置）；j>=line_n → 末尾 */
static int line_first(int j) {
    if (j < 0) return 0;
    if (j >= line_n) return -1;                 /* 末尾 */
    return lines[j].items[0].idx;
}

/* ================= 输入状态 ================= */
static char input_str[256]; static int input_len = 0;
static char completion[128];
static Camera2D camera;
static int first = 1;
static Vector2 mouse_world;
static Vector2 ptr_pos; static int has_ptr = 0;   /* 指针（最近间隙） */
static int edit_v = 0; static int edit_i = -1;    /* 悬浮编辑目标 */
static char edit_buf[256]; static int edit_len = 0;
static int pressed_combo = 0;                     /* 本次组合位：1=altl 2=altr 4=ctrl 8=shift */
static int prev_altl=0, prev_altr=0, prev_ctrl=0, prev_shift=0;
static int sel_start = -1; static int del_start = -1;
static Tok copy_buf[256]; static int copy_n = 0;
static int drag_sv = -1; static int ldrag = -1; static Vector2 ldrag_off;

/* ================= 补全候选：零大小 data 递归 collect（优先度=父×排名×大小）+ 插件名 ================= */
#define MAX_CAND 512
static char cands[MAX_CAND][64];
static int cand_prio[MAX_CAND];
static int cand_n = 0;
static int cand_ready = 0;

static void collect(BlockAPI *B, const uint8_t *key, u32 klen, int prio, int depth) {
    if (cand_n >= MAX_CAND || depth > 3) return;
    uint8_t names[256][64]; u32 nn = 0;
    B->load_names(key, klen, names, &nn, 256);
    for (u32 i = 0; i < nn && cand_n < MAX_CAND; i++) {
        int p = prio * (i + 1) * (int)strlen((char*)names[i]);
        if (p < 1) p = 1;
        strcpy(cands[cand_n], (char*)names[i]);
        cand_prio[cand_n++] = p;
        collect(B, names[i], (u32)strlen((char*)names[i]), p, depth + 1);
    }
}
static void build_cands(BlockAPI *B) {
    cand_n = 0;
    collect(B, (const uint8_t*)"", 0, 1, 0);            /* 零大小 data */
    for (size_t i = 0; i < PLUGIN_N && cand_n < MAX_CAND; i++) {  /* 插件名 */
        strcpy(cands[cand_n], PLUGINS[i]);
        cand_prio[cand_n++] = 10000;
    }
    /* 冒泡按优先度升序 */
    for (int i = 0; i < cand_n; i++)
        for (int j = i + 1; j < cand_n; j++)
            if (cand_prio[j] < cand_prio[i]) {
                char t[64]; strcpy(t, cands[i]); strcpy(cands[i], cands[j]); strcpy(cands[j], t);
                int tp = cand_prio[i]; cand_prio[i] = cand_prio[j]; cand_prio[j] = tp;
            }
    cand_ready = 1;
}

/* 补全：前缀匹配最优候选 */
static void update_completion(BlockAPI *B) {
    completion[0] = 0;
    if (!cand_ready) build_cands(B);
    if (input_len == 0) return;
    for (int i = 0; i < cand_n; i++) {
        if (strncmp(cands[i], input_str, input_len) == 0) {
            strcpy(completion, cands[i] + input_len); return;
        }
    }
}

/* ================= 编辑提交：复制 toks → cur_set（block 拥有新数组） ================= */
static void commit_toks(BlockAPI *B, View *v, Tok *nt, size_t nn) {
    B->cur_set(v->key, v->klen, nt, nn);
}

/* ================= 视图 toks 取用 ================= */
static Tok *view_toks(BlockAPI *B, int vi, size_t *out_n, Toks *fetched) {
    memset(fetched, 0, sizeof(*fetched));
    size_t n = 0;
    Tok *t = B->cur_get(views[vi].key, views[vi].klen, &n);
    if (t) { *out_n = n; return t; }
    *fetched = B->load_toks(views[vi].key, views[vi].klen);
    *out_n = fetched->n; return fetched->tok;
}
static void free_fetched(Toks *ts) {
    if (!ts->owned) return;
    for (size_t i = 0; i < ts->n; i++) { free(ts->tok[i].name); free(ts->tok[i].payload); }
    free(ts->tok);
}

/* ================= 渲染一个视图 ================= */
static void draw_view(BlockAPI *B, int vi) {
    View *v = &views[vi];
    Toks fetched; size_t n = 0;
    Tok *toks = view_toks(B, vi, &n, &fetched);
    build_lines(toks, n);

    /* 节点头（CRC 短名） */
    char kt[32]; crc_name(v->key, v->klen, kt);
    DrawText(kt, v->pos.x + 2, v->pos.y + 6, 13, C_HEAD);
    /* 父-子 LIME 连线 */
    if (v->src_v >= 0 && v->src_i >= 0 && v->src_i < anchor_n[v->src_v]) {
        DrawLineV(anchor[v->src_v][v->src_i], (Vector2){v->pos.x, v->pos.y + RH/2}, C_LINE);
    }
    /* 右键点击节点头 → 关闭（非主视图） */
    if (vi > 0 && IsMouseButtonPressed(MOUSE_BUTTON_RIGHT)
        && CheckCollisionPointRec(mouse_world, (Rectangle){v->pos.x, v->pos.y, 200, RH})) {
        v->klen = 0;
    }

    anchor_n[vi] = 0;
    for (int r = 0; r < line_n; r++) {
        Line *L = &lines[r];
        float y = row_y(v, r);
        for (int k = 0; k < L->n; k++) {
            Item *it = &L->items[k];
            Tok *t = &toks[it->idx];
            char lb[128]; item_label(t, lb);
            Color c = item_color(t);
            /* 锚点（连线/拖出用） */
            if (anchor_n[vi] <= it->idx) { while (anchor_n[vi] < it->idx) anchor[vi][anchor_n[vi]++] = (Vector2){v->pos.x + L->width, y}; anchor[vi][it->idx] = (Vector2){v->pos.x + it->x + 2, y}; anchor_n[vi] = it->idx + 1; }
            DrawText(lb, v->pos.x + it->x + 2, y, 20, c);
            /* handrun 双按钮 */
            if (name_is(t, "handrun")) {
                uint8_t b1, b2; B->hand_get(t->payload, &b1, &b2);
                float bx = v->pos.x + it->x + it->w - 22;
                DrawRectangle(bx, y, 10, 20, b1 ? C_GREEN : (Color){40,40,40,255});
                DrawRectangle(bx + 12, y, 10, 20, b2 ? C_GREEN : (Color){40,40,40,255});
            }
        }
    }
    v->end_y = v->pos.y + RH + (line_n > 0 ? line_n*(RH+GAP) : RH);
    if (line_n == 0) { anchor_n[vi] = 0; }
    free_fetched(&fetched);
}

/* ================= 交互 ================= */
/* 鼠标所在视图（含空白） */
static int hit_view(Vector2 w) {
    for (int i = view_n - 1; i >= 0; i--) {
        if (w.x >= views[i].pos.x - 20 && w.y >= views[i].pos.y - 6 && w.y <= views[i].end_y + 6)
            return i;
    }
    return -1;
}
/* 鼠标在视图内命中 item → token 索引（-1 无） */
static int hit_item(BlockAPI *B, int vi, Vector2 w) {
    size_t n; Toks fetched; Tok *toks = view_toks(B, vi, &n, &fetched);
    build_lines(toks, n);
    int hit = -1;
    for (int r = 0; r < line_n && hit < 0; r++) {
        float y = row_y(&views[vi], r);
        if (w.y < y - RH/2 || w.y > y + RH/2) continue;
        for (int k = 0; k < lines[r].n; k++) {
            Item *it = &lines[r].items[k];
            if (w.x >= views[vi].pos.x + it->x && w.x <= views[vi].pos.x + it->x + it->w) { hit = it->idx; break; }
        }
    }
    free_fetched(&fetched);
    return hit;
}

/* 悬浮编辑目标更新 */
static void update_edit(BlockAPI *B) {
    edit_v = cur_v;
    int i = hit_item(B, cur_v, mouse_world);
    size_t n; Toks f; Tok *ts = view_toks(B, cur_v, &n, &f);
    if (i >= 0 && (name_is(&ts[i],"read")||name_is(&ts[i],"set")||name_is(&ts[i],"cond")||name_is(&ts[i],"handrun")||name_is(&ts[i],"condrerun"))) {
        if (edit_i != i) { edit_i = i; edit_len = 0; edit_buf[0] = 0; }
    } else edit_i = -1;
    free_fetched(&f);
}

/* 插入位置（当前视图，鼠标最近间隙 → token 索引） */
static int insert_pos(BlockAPI *B) {
    size_t n; Toks f; Tok *ts = view_toks(B, cur_v, &n, &f);
    build_lines(ts, n);
    int j = nearest_gap(&views[cur_v], mouse_world.y, line_n);
    int p = line_first(j);
    free_fetched(&f);
    return p < 0 ? (int)n : p;
}

/* 视图 toks 深拷贝（编辑用：复制 + 修改后 cur_set） */
static Tok *dup_toks(Tok *src, size_t n) {
    Tok *nt = (Tok*)calloc(n + 1, sizeof(Tok));
    for (size_t i = 0; i < n; i++) {
        nt[i].name = (uint8_t*)malloc(src[i].nlen); memcpy(nt[i].name, src[i].name, src[i].nlen); nt[i].nlen = src[i].nlen;
        nt[i].payload = (uint8_t*)malloc(src[i].plen ? src[i].plen : 1); memcpy(nt[i].payload, src[i].payload, src[i].plen); nt[i].plen = src[i].plen;
    }
    return nt;
}

/* 空格插入：补全匹配用补全名，无匹配直接插入输入文本 */
static void space_insert(BlockAPI *B) {
    size_t n; Toks f; Tok *ts = view_toks(B, cur_v, &n, &f);
    Tok *nt = dup_toks(ts, n);
    int pos = insert_pos(B);
    char name[128] = "";
    int len = input_len;
    if (input_len > 0) {
        if (!cand_ready) build_cands(B);
        for (int i = 0; i < cand_n; i++) if (strncmp(cands[i], input_str, input_len) == 0) { strcpy(name, cands[i]); len = (int)strlen(name); break; }
        if (!name[0]) { memcpy(name, input_str, input_len); }
    }
    if (len == 0) { free(nt); free_fetched(&f); return; }
    /* 移动后面 token */
    for (int i = n; i > pos; i--) nt[i] = nt[i-1];
    nt[pos].name = (uint8_t*)malloc(len); memcpy(nt[pos].name, name, len); nt[pos].nlen = len;
    nt[pos].payload = (uint8_t*)malloc(1); nt[pos].plen = 0;
    commit_toks(B, &views[cur_v], nt, n + 1);
    input_len = 0; input_str[0] = 0; completion[0] = 0;
    free_fetched(&f);
}

/* 组合插入：左Alt=read 右Alt=set Ctrl=cond Ctrl+Alt=handrun Ctrl+Shift=condrerun */
static void combo_insert(BlockAPI *B, int combo) {
    size_t n; Toks f; Tok *ts = view_toks(B, cur_v, &n, &f);
    Tok *nt = dup_toks(ts, n);
    int pos = insert_pos(B);
    char name[16] = ""; uint8_t *payload = NULL; u32 plen = 0;
    if (combo & 1) strcpy(name, "read");
    else if (combo & 2) strcpy(name, "set");
    else if (combo & 4) {
        if (combo & 8) strcpy(name, "condrerun");
        else if (combo & 1) { strcpy(name, "handrun"); uint8_t id[8]; for (int i=0;i<8;i++) id[i]=(uint8_t)(rand()&0xff); payload=(uint8_t*)malloc(8); memcpy(payload,id,8); plen=8; B->hand_set(id,0,0); }
        else if (combo & 2) { strcpy(name, "handrun"); uint8_t id[8]; for (int i=0;i<8;i++) id[i]=(uint8_t)(rand()&0xff); payload=(uint8_t*)malloc(8); memcpy(payload,id,8); plen=8; B->hand_set(id,0,0); }
        else strcpy(name, "cond");
    }
    if (!name[0]) { free(nt); free_fetched(&f); return; }
    for (int i = n; i > pos; i--) nt[i] = nt[i-1];
    nt[pos].name = (uint8_t*)malloc(strlen(name)); memcpy(nt[pos].name, name, strlen(name)); nt[pos].nlen = (u32)strlen(name);
    nt[pos].payload = payload ? payload : (uint8_t*)malloc(1); nt[pos].plen = plen;
    commit_toks(B, &views[cur_v], nt, n + 1);
    free_fetched(&f);
}

/* 划选/删除/粘贴 */
static void sel_copy(BlockAPI *B) {
    int pos = insert_pos(B);
    int a = sel_start < pos ? sel_start : pos, b = sel_start < pos ? pos : sel_start;
    if (a >= b) return;
    size_t n; Toks f; Tok *ts = view_toks(B, cur_v, &n, &f);
    copy_n = b - a < 256 ? b - a : 256;
    for (int i = 0; i < copy_n; i++) {
        copy_buf[i].name = (uint8_t*)malloc(ts[a+i].nlen); memcpy(copy_buf[i].name, ts[a+i].name, ts[a+i].nlen); copy_buf[i].nlen = ts[a+i].nlen;
        copy_buf[i].payload = (uint8_t*)malloc(ts[a+i].plen ? ts[a+i].plen : 1); memcpy(copy_buf[i].payload, ts[a+i].payload, ts[a+i].plen); copy_buf[i].plen = ts[a+i].plen;
    }
    free_fetched(&f);
}
static void sel_del(BlockAPI *B) {
    int pos = insert_pos(B);
    int a = del_start < pos ? del_start : pos, b = del_start < pos ? pos : del_start;
    if (a >= b) return;
    size_t n; Toks f; Tok *ts = view_toks(B, cur_v, &n, &f);
    Tok *nt = dup_toks(ts, n);
    for (int i = a; i < b; i++) { free(nt[i].name); free(nt[i].payload); }
    for (int i = b; i < (int)n; i++) nt[i - (b-a)] = nt[i];
    commit_toks(B, &views[cur_v], nt, n - (b-a));
    free_fetched(&f);
}
static void paste(BlockAPI *B) {
    if (copy_n == 0) return;
    size_t n; Toks f; Tok *ts = view_toks(B, cur_v, &n, &f);
    int pos = insert_pos(B);
    Tok *nt = dup_toks(ts, n);
    /* 后面后移 */
    for (int i = n + copy_n - 1; i >= pos + copy_n; i--) nt[i] = nt[i - copy_n];
    for (int i = 0; i < copy_n; i++) {
        nt[pos+i].name = (uint8_t*)malloc(copy_buf[i].nlen); memcpy(nt[pos+i].name, copy_buf[i].name, copy_buf[i].nlen); nt[pos+i].nlen = copy_buf[i].nlen;
        nt[pos+i].payload = (uint8_t*)malloc(copy_buf[i].plen ? copy_buf[i].plen : 1); memcpy(nt[pos+i].payload, copy_buf[i].payload, copy_buf[i].plen); nt[pos+i].plen = copy_buf[i].plen;
    }
    commit_toks(B, &views[cur_v], nt, n + copy_n);
    free_fetched(&f);
}


/* 找到 token 在视图中的 item 世界矩形（handrun 按钮定位用） */
static int find_item_rect(BlockAPI *B, int vi, int idx, float *ox, float *oy, float *ow) {
    size_t n; Toks f; Tok *ts = view_toks(B, vi, &n, &f);
    build_lines(ts, n);
    int found = 0;
    for (int r = 0; r < line_n && !found; r++) {
        float y = row_y(&views[vi], r);
        for (int k = 0; k < lines[r].n; k++) {
            Item *it = &lines[r].items[k];
            if (it->idx == idx) { *ox = views[vi].pos.x + it->x; *oy = y; *ow = it->w; found = 1; break; }
        }
    }
    free_fetched(&f);
    return found;
}

/* 右键拖出：块引用 token → 新子视图（目标不存在上传 4B 零占位，待 block_api 扩展后启用上传） */
static void drag_out(BlockAPI *B, int vi, int i) {
    size_t n; Toks f; Tok *ts = view_toks(B, vi, &n, &f);
    if (i < 0 || i >= (int)n || has_plugin(ts[i].name, ts[i].nlen)) { free_fetched(&f); return; }
    if (view_n >= MAX_VIEW) { free_fetched(&f); return; }
    View *nv = &views[view_n];
    u32 kl = ts[i].nlen < 256 ? ts[i].nlen : 256;
    memcpy(nv->key, ts[i].name, kl); nv->klen = kl;
    /* 目标不存在 → 上传 4 字节全零占位 */
    {
        Toks ef = B->load_toks(nv->key, nv->klen);
        if (ef.n == 0) {
            uint8_t zero[4] = {0,0,0,0};
            B->net_upload_fn(nv->key, nv->klen, zero, 4);
        }
        free_fetched(&ef);
    }
    nv->pos = mouse_world; nv->src_v = vi; nv->src_i = i;
    view_n++;
    drag_sv = view_n - 1;
    free_fetched(&f);
}

/* 压缩关闭的视图 + 拖动 */
static void compact_views(void) {
    int w = 0;
    for (int i = 0; i < view_n; i++) {
        if (i > 0 && views[i].klen == 0) { if (drag_sv == i) drag_sv = -1; continue; }
        if (w != i) views[w] = views[i];
        w++;
    }
    view_n = w;
    if (drag_sv >= 0 && IsMouseButtonDown(MOUSE_BUTTON_RIGHT)) views[drag_sv].pos = mouse_world;
    else if (drag_sv >= 0) drag_sv = -1;
}

/* ================= 主循环 ================= */
__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    const uint8_t *ck; u32 ckl;
    B->cur_key_of(&ck, &ckl);
    if (first) {
        first = 0;
        SetTraceLogLevel(LOG_NONE);
        InitWindow(1000, 700, "Simply Editor");
        SetTargetFPS(60);
        srand((unsigned)GetTickCount());
        camera.zoom = 1.0f;
        View *v = &views[0];
        u32 kl = ckl < 256 ? ckl : 256;
        memcpy(v->key, ck ? ck : (const uint8_t*)"", kl); v->klen = kl;
        v->pos = (Vector2){40, 60}; v->src_v = -1; v->src_i = -1;
        view_n = 1;
        size_t n = 0;
        if (!B->cur_get(v->key, v->klen, &n)) {
            Toks ts = B->load_toks(v->key, v->klen);
            B->cur_set(v->key, v->klen, ts.tok, ts.n);
        }
    } else {
        u32 kl = ckl < 256 ? ckl : 256;
        memcpy(views[0].key, ck ? ck : (const uint8_t*)"", kl); views[0].klen = kl;
    }

    /* 输入收集 */
    int ch = GetCharPressed();
    while (ch > 0) { if (input_len < 250) { input_str[input_len++] = (char)ch; input_str[input_len] = 0; } ch = GetCharPressed(); }
    if (IsKeyPressed(KEY_BACKSPACE) && input_len > 0) input_str[--input_len] = 0;
    update_completion(B);

    /* 相机：滚轮缩放（鼠标锚点）+ 中键平移 */
    float wheel = GetMouseWheelMove();
    if (wheel != 0) {
        Vector2 before = GetScreenToWorld2D(GetMousePosition(), camera);
        camera.zoom += wheel * (0.1f * camera.zoom);
        camera.target = Vector2Add(before, Vector2Scale(Vector2Subtract(GetMousePosition(), (Vector2){GetScreenWidth()/2, GetScreenHeight()/2}), -1.0f/camera.zoom));
    }
    camera.offset = (Vector2){GetScreenWidth() / 2, GetScreenHeight() / 2};
    mouse_world = GetScreenToWorld2D(GetMousePosition(), camera);
    if (IsMouseButtonDown(MOUSE_BUTTON_MIDDLE))
        camera.target = Vector2Subtract(camera.target, Vector2Scale(GetMouseDelta(), 1.0f / camera.zoom));

    /* 当前视图 = 鼠标所在 */
    cur_v = hit_view(mouse_world); if (cur_v < 0) cur_v = 0;
    update_edit(B);

    /* 组合插入（松开判定） */
    {
        int altl = IsKeyDown(KEY_LEFT_ALT), altr = IsKeyDown(KEY_RIGHT_ALT);
        int ctrl = IsKeyDown(KEY_LEFT_CONTROL) || IsKeyDown(KEY_RIGHT_CONTROL);
        int shift = IsKeyDown(KEY_LEFT_SHIFT) || IsKeyDown(KEY_RIGHT_SHIFT);
        if (IsKeyPressed(KEY_LEFT_ALT)) { pressed_combo |= 1; }
        if (IsKeyPressed(KEY_RIGHT_ALT)) { pressed_combo |= 2; }
        if (IsKeyPressed(KEY_LEFT_CONTROL) || IsKeyPressed(KEY_RIGHT_CONTROL)) { pressed_combo |= 4; }
        if (IsKeyPressed(KEY_LEFT_SHIFT) || IsKeyPressed(KEY_RIGHT_SHIFT)) { pressed_combo |= 8; }
        if (!altl && !altr && !ctrl && !shift) {          /* 全部松开 → 判定 */
            if (pressed_combo) {
                if (edit_i < 0) combo_insert(B, pressed_combo);
                pressed_combo = 0;
            }
        }
        /* SHIFT 划选：按下记起点，松开复制 */
        if (IsKeyPressed(KEY_LEFT_SHIFT) || IsKeyPressed(KEY_RIGHT_SHIFT)) { if (!(ctrl)) sel_start = insert_pos(B); }
        if ((!shift) && sel_start >= 0) { sel_copy(B); sel_start = -1; }
        /* DELETE 划删：按下记起点，松开删 */
        if (IsKeyPressed(KEY_DELETE)) del_start = insert_pos(B);
        if (IsKeyReleased(KEY_DELETE) && del_start >= 0) { sel_del(B); del_start = -1; }
        /* INSERT 粘贴 */
        if (IsKeyPressed(KEY_INSERT)) paste(B);
        prev_altl = altl; prev_altr = altr; prev_ctrl = ctrl; prev_shift = shift;
    }

    /* 空格插入 */
    if (IsKeyPressed(KEY_SPACE)) space_insert(B);
    /* 回车补全确认（inp 替换为匹配） */
    if (IsKeyPressed(KEY_ENTER) && input_len > 0) {
        if (!cand_ready) build_cands(B);
        for (int i = 0; i < cand_n; i++)
            if (strncmp(cands[i], input_str, input_len) == 0) { strcpy(input_str, cands[i]); input_len = (int)strlen(input_str); break; }
    }
    /* ESC 关窗 */
    if (IsKeyPressed(KEY_ESCAPE)) exit(0);

    /* 悬浮编辑 payload：read/set/cond/condrerun/handrun 目标 */
    if (edit_i >= 0 && ch > 0) {
        size_t n; Toks f; Tok *ts = view_toks(B, edit_v, &n, &f);
        if (edit_len < 100) { edit_buf[edit_len++] = (char)ch; edit_buf[edit_len] = 0; }
        Tok *nt = dup_toks(ts, n);
        Tok *e = &nt[edit_i];
        if (name_is(e, "handrun")) {
            uint8_t id[8]; memcpy(id, e->payload, e->plen > 8 ? 8 : e->plen);
            free(e->payload); e->payload = (uint8_t*)malloc(8 + edit_len); memcpy(e->payload, id, 8); memcpy(e->payload + 8, edit_buf, edit_len); e->plen = 8 + edit_len;
        } else {
            free(e->payload); e->payload = (uint8_t*)malloc(edit_len ? edit_len : 1); memcpy(e->payload, edit_buf, edit_len); e->plen = edit_len;
        }
        commit_toks(B, &views[edit_v], nt, n);
        free_fetched(&f);
    }
    if (edit_i >= 0 && IsKeyPressed(KEY_ENTER)) edit_i = -1;

    /* 鼠标交互 */
    if (IsMouseButtonPressed(MOUSE_BUTTON_LEFT)) {
        ldrag = -1;
        int si = hit_view(mouse_world);
        if (si >= 0) {
            int i = hit_item(B, si, mouse_world);
            if (i >= 0) {
                size_t n; Toks f; Tok *ts = view_toks(B, si, &n, &f);
                if (name_is(&ts[i], "handrun")) {
                    float ox, oy, ow;
                    if (find_item_rect(B, si, i, &ox, &oy, &ow)) {
                        int relx = (int)(mouse_world.x - (ox + ow - 22));
                        uint8_t b1, b2; B->hand_get(ts[i].payload, &b1, &b2);
                        if (relx >= 0 && relx < 10) B->hand_set(ts[i].payload, b1 ? 0 : 1, b2);
                        else if (relx >= 12 && relx < 24) B->hand_set(ts[i].payload, b1, b2 ? 0 : 1);
                    }
                }
                free_fetched(&f);
            } else { ldrag = si; ldrag_off = Vector2Subtract(mouse_world, views[si].pos); }
        }
    }
    if (IsMouseButtonDown(MOUSE_BUTTON_LEFT) && ldrag >= 0) views[ldrag].pos = Vector2Subtract(mouse_world, ldrag_off);
    if (IsMouseButtonReleased(MOUSE_BUTTON_LEFT)) ldrag = -1;

    if (IsMouseButtonPressed(MOUSE_BUTTON_RIGHT)) {
        int si = hit_view(mouse_world);
        if (si >= 0) {
            int i = hit_item(B, si, mouse_world);
            if (i >= 0) drag_out(B, si, i);
        }
    }

    /* 渲染 */
    BeginDrawing();
    ClearBackground(C_BG);
    BeginMode2D(camera);
    for (int i = 0; i < view_n; i++) draw_view(B, i);
    /* 指针：鼠标所在视图最近间隙横线 */
    {
        size_t n; Toks f; Tok *ts = view_toks(B, cur_v, &n, &f);
        build_lines(ts, n);
        int j = nearest_gap(&views[cur_v], mouse_world.y, line_n);
        float gy = gap_y(&views[cur_v], j);
        DrawLine(views[cur_v].pos.x, gy, mouse_world.x, gy, C_PTR);
        free_fetched(&f);
    }
    EndMode2D();
    if (input_len > 0) {
        char tmp[400];
        sprintf(tmp, "%s%s", input_str, completion);
        DrawText(tmp, GetMouseX() + 20, GetMouseY(), 20, C_INP);
    }
    EndDrawing();

    compact_views();
    if (WindowShouldClose()) exit(0);
    B->reset();
}
