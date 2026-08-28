/* editor_lib.h —— 编辑器函数实现（对齐 .c 编辑器；全局状态收进 EState*，BlockAPI 经参数传入）
   插件薄包装 include 本文件 + plug_api.h + editor_state.h */
#ifndef EDITOR_LIB_H
#define EDITOR_LIB_H
#include "plug_api.h"
#include "editor_state.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

/* ---- 颜色（对齐 .c） ---- */
static const Color C_BG    = {15, 18, 24, 255};
static const Color C_DIM   = {70, 80, 90, 255};
static const Color C_HIT   = {90, 160, 220, 255};
static const Color C_GREEN = {98, 201, 130, 255};
static const Color C_YELLOW= {232, 200, 120, 255};
static const Color C_COND  = {208, 128, 224, 255};
static const Color C_HAND  = {247, 118, 142, 255};
static const Color C_CRUN  = {255, 158, 100, 255};
static const Color C_HEAD  = {120, 130, 145, 255};
static const Color C_PTR   = {0, 228, 48, 255};
static const Color C_INP   = {232, 236, 239, 255};
static const Color C_LINE  = {0, 255, 0, 255};

/* ---- 内嵌 sha256（has_plugin 判定 DLL 是否存在） ---- */
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
static inline void sha256(const uint8_t *d, uint32_t len, uint8_t out[32]) {
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
        uint32_t a=h[0],b=h[1],c=h[2],dd=h[3],e=h[4],f=h[5],g=h[6],hh=h[7];
        for (int i = 0; i < 64; i++) {
            uint32_t t1 = hh + SIG1(e) + CH(e,f,g) + K[i] + w[i];
            uint32_t t2 = SIG0(a) + MAJ(a,b,c);
            hh=g; g=f; f=e; e=dd+t1; dd=c; c=b; b=a; a=t1+t2;
        }
        h[0]+=a; h[1]+=b; h[2]+=c; h[3]+=dd; h[4]+=e; h[5]+=f; h[6]+=g; h[7]+=hh;
    }
    for (int i = 0; i < 8; i++) {
        out[i*4]   = (uint8_t)(h[i] >> 24);
        out[i*4+1] = (uint8_t)(h[i] >> 16);
        out[i*4+2] = (uint8_t)(h[i] >> 8);
        out[i*4+3] = (uint8_t)h[i];
    }
}

/* ---- CRC32（节点头短名/子视图同步） ---- */
static inline uint32_t crc32(const uint8_t *d, size_t len) {
    uint32_t c = 0xFFFFFFFF;
    for (size_t i = 0; i < len; i++) {
        c ^= d[i];
        for (int k = 0; k < 8; k++) c = (c >> 1) ^ (0xEDB88320 & -(c & 1));
    }
    return c ^ 0xFFFFFFFF;
}
static inline void crc_name(const uint8_t *key, u32 klen, char *out) {
    uint32_t n = crc32(key, klen);
    if (!n) n = 1;
    char rev[16]; int i = 0;
    while (n) { rev[i++] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"[n % 32]; n /= 32; }
    int j = 0; while (i) out[j++] = rev[--i];
    out[j] = 0;
}

/* ---- 名字/插件判定 ---- */
static inline int name_is(const Tok *t, const char *s) {
    size_t n = strlen(s);
    return t->nlen == n && memcmp(t->name, s, n) == 0;
}
extern unsigned int __stdcall GetFileAttributesA(const char *name);
static inline int has_plugin(const uint8_t *name, u32 n) {
    if (n == 0) return 0;                          /* 零长名 = 块引用（下钻空 key 编辑器块） */
    uint8_t h[32]; sha256(name, n, h);
    char fn[70];
    for (int i = 0; i < 32; i++) sprintf(fn + 2*i, "%02x", h[i]);
    strcat(fn, ".dll");
    return GetFileAttributesA(fn) != 0xFFFFFFFF;
}

/* ---- 显示文本/宽度/颜色 ---- */
static inline void item_label(const Tok *t, char *out) {
    if (t->nlen == 0) { strcpy(out, "(editor)"); return; }
    if (name_is(t, "handrun")) {
        u32 pl = t->plen > 8 ? t->plen - 8 : 0;
        if (pl == 0) { strcpy(out, "handrun"); return; }
        u32 c = pl < 100 ? pl : 100;
        memcpy(out, t->payload + 8, c); out[c] = 0;
        return;
    }
    if ((name_is(t,"read")||name_is(t,"set")||name_is(t,"cond")||name_is(t,"condrerun")||name_is(t,"push_int")) && t->plen > 0) {
        u32 c = t->plen < 100 ? t->plen : 100;
        memcpy(out, t->payload, c); out[c] = 0;
        return;
    }
    u32 c = t->nlen < 100 ? t->nlen : 100;
    memcpy(out, t->name, c); out[c] = 0;
}
static inline float item_w(const Tok *t) {
    char lb[128]; item_label(t, lb);
    float w = MeasureText(lb, 20) + 20;
    if (name_is(t, "handrun")) w += 26;
    return w;
}
static inline Color heat_color(Color base, u32 heat) {
    if (!heat) return base;
    float f = heat * 0.2f; if (f > 1.0f) f = 1.0f;
    return (Color){ (uint8_t)(base.r + (255 - base.r)*f), (uint8_t)(base.g + (80 - base.g)*f), (uint8_t)(base.b + (80 - base.b)*f), 255 };
}
static inline Color item_color(BlockAPI *B, const Tok *t) {
    if (name_is(t,"read")) return C_GREEN;
    if (name_is(t,"set")) return C_YELLOW;
    if (name_is(t,"cond")) return heat_color(C_COND, B->heat_get(t->name, t->nlen));
    if (name_is(t,"handrun")) return heat_color(C_HAND, B->heat_get(t->name, t->nlen));
    if (name_is(t,"condrerun")) return heat_color(C_CRUN, B->heat_get(t->name, t->nlen));
    if (t->nlen == 0) return C_HIT;
    return has_plugin(t->name, t->nlen) ? C_HIT : C_DIM;
}

/* ---- 行布局 ---- */
static inline void build_lines(EState *e, Tok *toks, size_t n) {
    e->line_n = 0; int left[32]; int left_n = 0;
    for (size_t i = 0; i < n; i++) {
        if (name_is(&toks[i], "read")) { if (left_n < 32) left[left_n++] = (int)i; }
        else if (name_is(&toks[i], "set")) {
            if (e->line_n > 0) { Line *L = &e->lines[e->line_n-1]; if (L->n < 32) L->items[L->n++] = (Item){2, (int)i, 0, item_w(&toks[i])}; }
            else if (left_n < 32) left[left_n++] = (int)i;
        }
        else {
            if (e->line_n >= MAX_LINE) break;
            Line *L = &e->lines[e->line_n++];
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
    if (left_n > 0 && e->line_n < MAX_LINE) {
        Line *L = &e->lines[e->line_n++]; L->n = 0; L->width = 0;
        for (int k = 0; k < left_n; k++) {
            L->items[L->n++] = (Item){0, left[k], 0, item_w(&toks[left[k]])};
            L->width += L->items[L->n-1].w + 6;
        }
    }
    for (int r = 0; r < e->line_n; r++) {
        float x = 0;
        for (int k = 0; k < e->lines[r].n; k++) { e->lines[r].items[k].x = x; x += e->lines[r].items[k].w + 6; }
    }
}

/* ---- 行几何 ---- */
static inline float row_y(const View *v, int row) { return v->pos.y + RH + row*(RH+GAP) + RH/2; }
static inline float gap_y(const View *v, int j, int line_n) {
    if (j <= 0) return (v->pos.y + RH + row_y(v, 0)) / 2;
    if (j >= line_n) return row_y(v, line_n - 1) + TEXT_H + GAP;
    return (row_y(v, j - 1) + TEXT_H + row_y(v, j)) / 2;
}
static inline int nearest_gap(const View *v, float wy, int maxj, int line_n) {
    int best = 0; float bd = 1e9f;
    for (int j = 0; j <= maxj; j++) {
        float d = gap_y(v, j, line_n) - wy; if (d < 0) d = -d;
        if (d < bd) { bd = d; best = j; }
    }
    return best;
}
static inline int line_first(EState *e, int j) {
    if (j < 0) return 0;
    if (j >= e->line_n) return -1;
    return e->lines[j].items[0].idx;
}

/* ---- 视图 toks / 复制 / 提交 ---- */
static inline Tok *view_toks(BlockAPI *B, EState *e, int vi, size_t *out_n, Toks *fetched) {
    /* raw-ptr-editor：直接解析 ptr 指向的原始块字节；Tok 只是显示期临时视图，不拷贝。 */
    memset(fetched, 0, sizeof(*fetched));
    static Tok parsed[256];
    static Toks holder = {0};
    const uint8_t *raw = NULL; u32 raw_len = 0;
    raw = B->raw_get(e->views[vi].key, e->views[vi].klen, &raw_len);
    size_t n = 0; u32 off = 0;
    while (off + 4 <= raw_len && n < 256) {
        u32 nl; memcpy(&nl, raw + off, 4);
        if (nl == 0xFFFFFFFFu) break;                 /* ENDMK */
        off += 4;
        if (off + nl + 4 > raw_len) break;
        parsed[n].name = (uint8_t*)raw + off; parsed[n].nlen = nl; off += nl;
        u32 dl; memcpy(&dl, raw + off, 4); off += 4;
        parsed[n].payload = (uint8_t*)raw + off; parsed[n].plen = dl; off += dl;
        n++;
    }
    holder.tok = parsed; holder.n = n; holder.cap = 256; holder.owned = 0;
    *fetched = holder;
    *out_n = n;
    return parsed;
}
static inline void free_fetched(Toks *ts) {
    if (!ts->owned) return;
    for (size_t i = 0; i < ts->n; i++) { free(ts->tok[i].name); free(ts->tok[i].payload); }
    free(ts->tok);
}
static inline Tok *dup_toks(Tok *src, size_t n) {
    Tok *nt = (Tok*)calloc(n + 1, sizeof(Tok));
    for (size_t i = 0; i < n; i++) {
        nt[i].name = (uint8_t*)malloc(src[i].nlen); memcpy(nt[i].name, src[i].name, src[i].nlen); nt[i].nlen = src[i].nlen;
        nt[i].payload = (uint8_t*)malloc(src[i].plen ? src[i].plen : 1); memcpy(nt[i].payload, src[i].payload, src[i].plen); nt[i].plen = src[i].plen;
    }
    return nt;
}
static inline void commit_toks(BlockAPI *B, View *v, Tok *nt, size_t nn) {
    B->cur_set(v->key, v->klen, nt, nn);
}

/* ---- 节点头文字 ---- */
static inline void header_text(const View *v, char *out) {
    int printable = v->klen > 0;
    for (u32 i = 0; i < v->klen; i++)
        if (v->key[i] < 0x20 || v->key[i] > 0x7E) { printable = 0; break; }
    if (printable) {
        u32 c = v->klen < 200 ? v->klen : 200;
        memcpy(out, v->key, c); out[c] = 0;
    } else {
        u32 c = v->klen < 16 ? v->klen : 16;
        for (u32 i = 0; i < c; i++) sprintf(out + 2*i, "%02x", v->key[i]);
        if (v->klen > c) strcat(out, "...");
    }
}

/* ---- 命中视图 / item ---- */
static inline int hit_view(EState *e, Vector2 w) {
    for (int i = e->view_n - 1; i >= 0; i--) {
        if (w.x >= e->views[i].pos.x - 20 && w.y >= e->views[i].pos.y - 6 && w.y <= e->views[i].end_y + 6)
            return i;
    }
    return -1;
}
static inline int hit_item(BlockAPI *B, EState *e, int vi, Vector2 w) {
    size_t n; Toks fetched; Tok *toks = view_toks(B, e, vi, &n, &fetched);
    build_lines(e, toks, n);
    int hit = -1;
    for (int r = 0; r < e->line_n && hit < 0; r++) {
        float y = row_y(&e->views[vi], r);
        if (w.y < y + TOFF - RH/2 || w.y > y + TOFF + RH/2) continue;
        for (int k = 0; k < e->lines[r].n; k++) {
            Item *it = &e->lines[r].items[k];
            if (w.x >= e->views[vi].pos.x + it->x && w.x <= e->views[vi].pos.x + it->x + it->w) { hit = it->idx; break; }
        }
    }
    free_fetched(&fetched);
    return hit;
}
static inline void update_edit(BlockAPI *B, EState *e) {
    e->edit_v = e->cur_v;
    int i = hit_item(B, e, e->cur_v, e->mouse_world);
    size_t n; Toks f; Tok *ts = view_toks(B, e, e->cur_v, &n, &f);
    if (i >= 0 && (name_is(&ts[i],"read")||name_is(&ts[i],"set")||name_is(&ts[i],"cond")||name_is(&ts[i],"handrun")||name_is(&ts[i],"condrerun")||name_is(&ts[i],"push_int"))) {
        if (e->edit_i != i) { e->edit_i = i; e->edit_len = 0; e->edit_buf[0] = 0; }
    } else e->edit_i = -1;
    free_fetched(&f);
}

/* ---- 指针定位 ---- */
static inline int pointer_locate(BlockAPI *B, EState *e, float *ox, float *oy) {
    size_t n; Toks f; Tok *ts = view_toks(B, e, e->cur_v, &n, &f);
    build_lines(e, ts, n);
    View *v = &e->views[e->cur_v];
    int pos = (int)n;
    int inrow = 0;
    for (int r = 0; r < e->line_n; r++) {
        float y = row_y(v, r);
        if (e->mouse_world.y < y + TOFF - RH/2 || e->mouse_world.y > y + TOFF + RH/2) continue;
        inrow = 1;
        *oy = y;
        *ox = v->pos.x;
        pos = (int)n;
        for (int k = 0; k < e->lines[r].n; k++) {
            Item *it = &e->lines[r].items[k];
            float x0 = v->pos.x + it->x;
            if (e->mouse_world.x < x0 + it->w / 2) { pos = it->idx; *ox = x0; break; }
            pos = it->idx + 1;
            *ox = x0 + it->w;
        }
        break;
    }
    if (!inrow) {
        int j = nearest_gap(v, e->mouse_world.y, e->line_n, e->line_n);
        pos = line_first(e, j);
        if (pos < 0) pos = (int)n;
        *ox = v->pos.x;
        *oy = gap_y(v, j, e->line_n);
    }
    free_fetched(&f);
    return pos;
}
static inline int pointer_pos(BlockAPI *B, EState *e) {
    float x, y;
    return pointer_locate(B, e, &x, &y);
}

/* ---- 补全候选 ---- */
static const char *PLUGINS[] = {
    "boot","editor","rerun","add","read","set","cond","handrun","condrerun",
    "push_int","in-int","out","rand","gt","lt","eq","mul","ret_int"
};
#define PLUGIN_N (sizeof(PLUGINS)/sizeof(PLUGINS[0]))
static inline void collect_cands(BlockAPI *B, EState *e, const uint8_t *key, u32 klen, int prio, int depth) {
    if (e->cand_n >= MAX_CAND || depth > 3) return;
    uint8_t names[256][64]; u32 nn = 0;
    B->load_names(key, klen, names, &nn, 256);
    for (u32 i = 0; i < nn && e->cand_n < MAX_CAND; i++) {
        int p = prio * (i + 1) * (int)strlen((char*)names[i]);
        if (p < 1) p = 1;
        strcpy(e->cands[e->cand_n], (char*)names[i]);
        e->cand_prio[e->cand_n++] = p;
        collect_cands(B, e, names[i], (u32)strlen((char*)names[i]), p, depth + 1);
    }
}
static inline void build_cands(BlockAPI *B, EState *e) {
    e->cand_n = 0;
    collect_cands(B, e, (const uint8_t*)"", 0, 1, 0);
    for (size_t i = 0; i < PLUGIN_N && e->cand_n < MAX_CAND; i++) {
        strcpy(e->cands[e->cand_n], PLUGINS[i]);
        e->cand_prio[e->cand_n++] = 10000;
    }
    for (int i = 0; i < e->cand_n; i++)
        for (int j = i + 1; j < e->cand_n; j++)
            if (e->cand_prio[j] < e->cand_prio[i]) {
                char t[64]; strcpy(t, e->cands[i]); strcpy(e->cands[i], e->cands[j]); strcpy(e->cands[j], t);
                int tp = e->cand_prio[i]; e->cand_prio[i] = e->cand_prio[j]; e->cand_prio[j] = tp;
            }
    e->cand_ready = 1;
}
static inline void update_completion(BlockAPI *B, EState *e) {
    e->completion[0] = 0;
    if (!e->cand_ready) build_cands(B, e);
    if (e->input_len == 0) return;
    for (int i = 0; i < e->cand_n; i++) {
        if (strncmp(e->cands[i], e->input_str, e->input_len) == 0) {
            strcpy(e->completion, e->cands[i] + e->input_len); return;
        }
    }
}

/* ---- raw 编辑辅助前置声明 ---- */
static inline int raw_tok_count(const uint8_t *raw, u32 raw_len);
static inline int raw_tok_bounds(const uint8_t *raw, u32 raw_len, int idx, u32 *tok_off, u32 *nl, u32 *payload_off, u32 *plen);
static inline void raw_insert_token(BlockAPI *B, EState *e, int vi, int idx, const uint8_t *name, u32 nl, const uint8_t *payload, u32 pl);

/* ---- 编辑操作 ---- */
static inline void space_insert(BlockAPI *B, EState *e) {
    int pos = pointer_pos(B, e);
    char name[128] = "";
    int len = e->input_len;
    if (e->input_len > 0) {
        if (!e->cand_ready) build_cands(B, e);
        for (int i = 0; i < e->cand_n; i++) if (strncmp(e->cands[i], e->input_str, e->input_len) == 0) { strcpy(name, e->cands[i]); len = (int)strlen(name); break; }
        if (!name[0]) { memcpy(name, e->input_str, e->input_len); }
        while (len > 0 && name[len-1] == ' ') len--;
    }
    if (len == 0) return;
    raw_insert_token(B, e, e->cur_v, pos, (const uint8_t*)name, (u32)len, NULL, 0);
    e->input_len = 0; e->input_str[0] = 0; e->completion[0] = 0;
}
static inline void combo_insert(BlockAPI *B, EState *e, int combo) {
    int pos = pointer_pos(B, e);
    char name[16] = ""; uint8_t local_payload[8]; uint8_t *payload = NULL; u32 plen = 0;
    if ((combo & 4) && (combo & 3)) {
        strcpy(name, "handrun");
        for (int i=0;i<8;i++) local_payload[i]=(uint8_t)(rand()&0xff);
        B->hand_set(local_payload,0,0);
        payload = local_payload; plen = 8;
    } else if ((combo & 4) && (combo & 8)) strcpy(name, "condrerun");
    else if (combo & 4) strcpy(name, "cond");
    else if (combo & 1) strcpy(name, "read");
    else if (combo & 2) strcpy(name, "set");
    if (!name[0]) return;
    raw_insert_token(B, e, e->cur_v, pos, (const uint8_t*)name, (u32)strlen(name), payload, plen);
}
static inline void sel_copy(BlockAPI *B, EState *e) {
    int pos = pointer_pos(B, e);
    int a = e->sel_start < pos ? e->sel_start : pos, b = e->sel_start < pos ? pos : e->sel_start;
    if (a >= b) return;
    size_t n; Toks f; Tok *ts = view_toks(B, e, e->cur_v, &n, &f);
    e->copy_n = b - a < 256 ? b - a : 256;
    for (int i = 0; i < e->copy_n; i++) {
        e->copy_buf[i].name = (uint8_t*)malloc(ts[a+i].nlen); memcpy(e->copy_buf[i].name, ts[a+i].name, ts[a+i].nlen); e->copy_buf[i].nlen = ts[a+i].nlen;
        e->copy_buf[i].payload = (uint8_t*)malloc(ts[a+i].plen ? ts[a+i].plen : 1); memcpy(e->copy_buf[i].payload, ts[a+i].payload, ts[a+i].plen); e->copy_buf[i].plen = ts[a+i].plen;
    }
    free_fetched(&f);
}
static inline void sel_del(BlockAPI *B, EState *e) {
    int pos = pointer_pos(B, e);
    int a = e->del_start < pos ? e->del_start : pos, b = e->del_start < pos ? pos : e->del_start;
    if (a >= b) return;
    size_t n; Toks f; Tok *ts = view_toks(B, e, e->cur_v, &n, &f);
    Tok *nt = dup_toks(ts, n);
    for (int i = a; i < b; i++) { free(nt[i].name); free(nt[i].payload); }
    for (int i = b; i < (int)n; i++) nt[i - (b-a)] = nt[i];
    commit_toks(B, &e->views[e->cur_v], nt, n - (b-a));
    free_fetched(&f);
}
static inline void paste(BlockAPI *B, EState *e) {
    if (e->copy_n == 0) return;
    size_t n; Toks f; Tok *ts = view_toks(B, e, e->cur_v, &n, &f);
    int pos = pointer_pos(B, e);
    Tok *nt = dup_toks(ts, n);
    for (int i = n + e->copy_n - 1; i >= pos + e->copy_n; i--) nt[i] = nt[i - e->copy_n];
    for (int i = 0; i < e->copy_n; i++) {
        nt[pos+i].name = (uint8_t*)malloc(e->copy_buf[i].nlen); memcpy(nt[pos+i].name, e->copy_buf[i].name, e->copy_buf[i].nlen); nt[pos+i].nlen = e->copy_buf[i].nlen;
        nt[pos+i].payload = (uint8_t*)malloc(e->copy_buf[i].plen ? e->copy_buf[i].plen : 1); memcpy(nt[pos+i].payload, e->copy_buf[i].payload, e->copy_buf[i].plen); nt[pos+i].plen = e->copy_buf[i].plen;
    }
    commit_toks(B, &e->views[e->cur_v], nt, n + e->copy_n);
    free_fetched(&f);
}
static inline int raw_tok_count(const uint8_t *raw, u32 raw_len) {
    u32 off = 0; int n = 0;
    while (off + 4 <= raw_len) {
        u32 nl; memcpy(&nl, raw + off, 4);
        if (nl == 0xFFFFFFFFu) break;
        off += 4;
        if (off + nl + 4 > raw_len) break;
        off += nl;
        u32 dl; memcpy(&dl, raw + off, 4); off += 4 + dl;
        n++;
    }
    return n;
}
static inline int raw_tok_bounds(const uint8_t *raw, u32 raw_len, int idx,
                                 u32 *tok_off, u32 *nl, u32 *payload_off, u32 *plen) {
    u32 off = 0; int n = 0;
    while (off + 4 <= raw_len) {
        u32 name_len; memcpy(&name_len, raw + off, 4);
        if (name_len == 0xFFFFFFFFu) break;
        u32 to = off; off += 4;
        if (off + name_len + 4 > raw_len) break;
        off += name_len;
        u32 dl; memcpy(&dl, raw + off, 4); off += 4;
        if (n == idx) {
            *tok_off = to; *nl = name_len; *payload_off = off; *plen = dl;
            return 1;
        }
        off += dl; n++;
    }
    return 0;
}
static inline void raw_replace_payload(BlockAPI *B, EState *e, int vi, int idx,
                                       const uint8_t *newp, u32 newp_len) {
    const uint8_t *raw = NULL; u32 raw_len = 0;
    raw = B->raw_get(e->views[vi].key, e->views[vi].klen, &raw_len);
    u32 tok_off = 0, nl = 0, payload_off = 0, plen = 0;
    if (!raw_tok_bounds(raw, raw_len, idx, &tok_off, &nl, &payload_off, &plen)) return;
    u32 plen_field_off = payload_off - 4;          /* 原 plen 字段紧接在 name 之后 */
    u32 old_end = payload_off + plen;
    if (old_end > raw_len) return;
    u32 new_len = raw_len - plen + newp_len;
    uint8_t *buf = (uint8_t*)malloc(new_len ? new_len : 1);
    memcpy(buf, raw, plen_field_off);              /* [nlen][name] 原样 */
    memcpy(buf + plen_field_off, &newp_len, 4);    /* 写新 plen */
    if (newp_len) memcpy(buf + payload_off, newp, newp_len);
    memcpy(buf + payload_off + newp_len, raw + old_end, raw_len - old_end); /* 后半段含 ENDMK */
    B->raw_set(e->views[vi].key, e->views[vi].klen, buf, new_len);
    free(buf);
}
static inline void raw_insert_token(BlockAPI *B, EState *e, int vi, int idx,
                                     const uint8_t *name, u32 nl, const uint8_t *payload, u32 pl) {
    const uint8_t *raw = NULL; u32 raw_len = 0;
    raw = B->raw_get(e->views[vi].key, e->views[vi].klen, &raw_len);
    u32 ins = (raw_len >= 4) ? raw_len - 4 : 0;   /* 默认插到 ENDMK 前=末尾 */
    u32 off = 0; int n = 0;
    while (off + 4 <= raw_len) {
        u32 name_len; memcpy(&name_len, raw + off, 4);
        if (name_len == 0xFFFFFFFFu) { ins = off; break; }
        if (n == idx) { ins = off; break; }
        off += 4 + name_len;
        if (off + 4 > raw_len) break;
        u32 dl; memcpy(&dl, raw + off, 4); off += 4 + dl;
        n++;
    }
    u32 new_len = raw_len + 4 + nl + 4 + pl;
    uint8_t *buf = (uint8_t*)malloc(new_len ? new_len : 1);
    memcpy(buf, raw, ins);
    u32 p = ins;
    memcpy(buf + p, &nl, 4); p += 4;
    if (nl) memcpy(buf + p, name, nl); p += nl;
    memcpy(buf + p, &pl, 4); p += 4;
    if (pl) memcpy(buf + p, payload, pl); p += pl;
    memcpy(buf + p, raw + ins, raw_len - ins);
    B->raw_set(e->views[vi].key, e->views[vi].klen, buf, new_len);
    free(buf);
}
static inline void edit_append(BlockAPI *B, EState *e, int ch) {
    if (e->edit_len < 100) { e->edit_buf[e->edit_len++] = (char)ch; e->edit_buf[e->edit_len] = 0; }
    const uint8_t *raw = NULL; u32 raw_len = 0;
    raw = B->raw_get(e->views[e->edit_v].key, e->views[e->edit_v].klen, &raw_len);
    int n = raw_tok_count(raw, raw_len);
    if (e->edit_i < n) {
        u32 tok_off = 0, nl = 0, payload_off = 0, plen = 0;
        if (!raw_tok_bounds(raw, raw_len, e->edit_i, &tok_off, &nl, &payload_off, &plen)) return;
        int hand = (nl == 7 && memcmp(raw + tok_off + 4, "handrun", 7) == 0);
        if (hand) {
            uint8_t nb[108];
            u32 id_len = plen > 8 ? 8 : plen;
            if (id_len) memcpy(nb, raw + payload_off, id_len);
            if (e->edit_len) memcpy(nb + 8, e->edit_buf, e->edit_len);
            raw_replace_payload(B, e, e->edit_v, e->edit_i, nb, 8 + e->edit_len);
        } else {
            raw_replace_payload(B, e, e->edit_v, e->edit_i,
                                (const uint8_t*)e->edit_buf, e->edit_len);
        }
    }
}static inline void inp_append(EState *e, int ch) {
    if (e->input_len < 250) { e->input_str[e->input_len++] = (char)ch; e->input_str[e->input_len] = 0; }
}
static inline void inp_backspace(EState *e) {
    if (e->input_len > 0) e->input_str[--e->input_len] = 0;
}

/* ---- 矩形定位（handrun 按钮） ---- */
static inline int find_item_rect(BlockAPI *B, EState *e, int vi, int idx, float *ox, float *oy, float *ow) {
    size_t n; Toks f; Tok *ts = view_toks(B, e, vi, &n, &f);
    build_lines(e, ts, n);
    int found = 0;
    for (int r = 0; r < e->line_n && !found; r++) {
        float y = row_y(&e->views[vi], r);
        for (int k = 0; k < e->lines[r].n; k++) {
            Item *it = &e->lines[r].items[k];
            if (it->idx == idx) { *ox = e->views[vi].pos.x + it->x; *oy = y; *ow = it->w; found = 1; break; }
        }
    }
    free_fetched(&f);
    return found;
}

/* ---- 右键拖出子视图 ---- */
static inline void drag_out(BlockAPI *B, EState *e, int vi, int i) {
    size_t n; Toks f; Tok *ts = view_toks(B, e, vi, &n, &f);
    if (i < 0 || i >= (int)n) { free_fetched(&f); return; }
    const uint8_t *key; u32 klen;
    if (name_is(&ts[i], "handrun")) {
        if (ts[i].plen <= 8) { free_fetched(&f); return; }
        key = ts[i].payload + 8; klen = ts[i].plen - 8;
        if (klen == 0) { free_fetched(&f); return; }
    } else if (has_plugin(ts[i].name, ts[i].nlen)) { free_fetched(&f); return; }
    else { key = ts[i].name; klen = ts[i].nlen; }
    if (e->view_n >= MAX_VIEW) { free_fetched(&f); return; }
    View *nv = &e->views[e->view_n];
    u32 kl = klen < 256 ? klen : 256;
    memcpy(nv->key, key, kl); nv->klen = kl;
    {
        Toks ef = B->load_toks(nv->key, nv->klen);
        if (ef.n == 0) {
            u32 endmk = 0xFFFFFFFFu;
            B->net_upload_fn(nv->key, nv->klen, (const uint8_t*)&endmk, 4);
        }
        free_fetched(&ef);
    }
    nv->pos = e->mouse_world; nv->src_v = vi; nv->src_i = i;
    e->view_n++;
    e->drag_sv = e->view_n - 1;
    free_fetched(&f);
}

/* ---- 子视图同步 / 压缩 ---- */
static inline void sync_views(BlockAPI *B, EState *e) {
    for (int vi = 1; vi < e->view_n; vi++) {
        size_t n; Toks f; Tok *ts = view_toks(B, e, vi, &n, &f);
        u32 sz = 4;
        for (size_t i = 0; i < n; i++) sz += 4 + ts[i].nlen + 4 + ts[i].plen;
        uint8_t *buf = (uint8_t*)malloc(sz ? sz : 1);
        u32 off = 0;
        for (size_t i = 0; i < n; i++) {
            memcpy(buf + off, &ts[i].nlen, 4); off += 4;
            memcpy(buf + off, ts[i].name, ts[i].nlen); off += ts[i].nlen;
            memcpy(buf + off, &ts[i].plen, 4); off += 4;
            memcpy(buf + off, ts[i].payload, ts[i].plen); off += ts[i].plen;
        }
        u32 z = 0xFFFFFFFFu; memcpy(buf + off, &z, 4);
        u32 c = crc32(buf, sz);
        if (c != e->view_crc[vi]) {
            B->net_upload_fn(e->views[vi].key, e->views[vi].klen, buf, sz);
            e->view_crc[vi] = c;
        }
        free(buf);
        free_fetched(&f);
    }
}
static inline void compact_views(EState *e) {
    int w = 0;
    for (int i = 0; i < e->view_n; i++) {
        if (i > 0 && e->views[i].klen == 0) { if (e->drag_sv == i) e->drag_sv = -1; continue; }
        if (w != i) e->views[w] = e->views[i];
        w++;
    }
    e->view_n = w;
    if (e->drag_sv >= 0 && IsMouseButtonDown(MOUSE_BUTTON_RIGHT)) e->views[e->drag_sv].pos = e->mouse_world;
    else if (e->drag_sv >= 0) e->drag_sv = -1;
}

/* ---- 渲染一个视图 ---- */
static inline void draw_view(BlockAPI *B, EState *e, int vi) {
    View *v = &e->views[vi];
    Toks fetched; size_t n = 0;
    Tok *toks = view_toks(B, e, vi, &n, &fetched);
    build_lines(e, toks, n);

    char kt[256]; header_text(v, kt);
    DrawText(kt, v->pos.x + 2, v->pos.y + 6, 13, C_HEAD);
    if (v->src_v >= 0 && v->src_i >= 0 && v->src_i < e->anchor_n[v->src_v]) {
        DrawLineV(e->anchor[v->src_v][v->src_i], (Vector2){v->pos.x, v->pos.y}, C_LINE);
    }
    e->anchor_n[vi] = 0;
    for (int r = 0; r < e->line_n; r++) {
        Line *L = &e->lines[r];
        float y = row_y(v, r);
        for (int k = 0; k < L->n; k++) {
            Item *it = &L->items[k];
            Tok *t = &toks[it->idx];
            char lb[128]; item_label(t, lb);
            Color c = item_color(B, t);
            if (e->anchor_n[vi] <= it->idx) {
                while (e->anchor_n[vi] < it->idx) e->anchor[vi][e->anchor_n[vi]++] = (Vector2){v->pos.x + L->width, y};
                e->anchor[vi][it->idx] = (Vector2){v->pos.x + it->x + 2 + MeasureText(lb, 20), y + TOFF};
                e->anchor_n[vi] = it->idx + 1;
            }
            DrawText(lb, v->pos.x + it->x + 2, y, 20, c);
            if (name_is(t, "handrun")) {
                uint8_t b1, b2; B->hand_get(t->payload, &b1, &b2);
                float bx = v->pos.x + it->x + it->w - 22;
                DrawRectangle(bx, y + TOFF, 10, 20, b1 ? C_GREEN : (Color){40,40,40,255});
                DrawRectangle(bx + 12, y + TOFF, 10, 20, b2 ? C_GREEN : (Color){40,40,40,255});
            }
        }
    }
    v->end_y = v->pos.y + RH + (e->line_n > 0 ? e->line_n*(RH+GAP) : RH);
    if (e->line_n == 0) { e->anchor_n[vi] = 0; }
    free_fetched(&fetched);
}
#endif
