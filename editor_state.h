/* editor_state.h —— 编辑器全局状态布局（EState：一次 calloc，指针存全局变量 "estate"）
   对齐 .c 编辑器的 static 全局：views/lines/anchor/cands/copy_buf/输入与交互状态全部集中于此 */
#ifndef EDITOR_STATE_H
#define EDITOR_STATE_H
#include "plug_api.h"
#include "raylib.h"
#include "raymath.h"
#include <stdint.h>
#include <stddef.h>

typedef uint32_t u32;
/* Tok/Toks 由 plug_api.h 提供（先 include 它） */

#define MAX_VIEW 64
#define MAX_LINE 512
#define MAX_ITEM 1024
#define MAX_CAND 512
#define RH 20.0f
#define GAP 4.0f
#define TEXT_H 18.0f
#define TOFF 8.0f

/* 视图：key(256) klen pos(8) src_v src_i end_y */
typedef struct {
    uint8_t key[256]; u32 klen;
    Vector2 pos;
    int src_v; int src_i;
    float end_y;
} View;

/* 行布局项与行（对齐 .c build_lines） */
typedef struct { int kind; int idx; float x; float w; } Item;
typedef struct { Item items[32]; int n; float width; } Line;

typedef struct {
    Camera2D camera;                             /* 相机 */
    Vector2 mouse_world;                         /* 鼠标世界坐标 */
    Vector2 ptr_pos; u32 has_ptr;                /* 指针位置 */
    int cur_v;                                   /* 当前编辑目标视图 */
    int edit_v; int edit_i; char edit_buf[256]; u32 edit_len;   /* 悬浮编辑 payload */
    char input_str[256]; u32 input_len;          /* 输入文本 */
    char completion[128];                        /* 补全后缀 */
    int pressed_combo, prev_altl, prev_altr, prev_ctrl, prev_shift;  /* 组合键状态 */
    int sel_start, del_start;                    /* 划选/划删起点 */
    uint8_t copy_buf[8192]; u32 copy_len;               /* 复制缓冲 */
    int drag_sv, ldrag; Vector2 ldrag_off;       /* 拖出/左拖状态 */
    u32 prev_rb, prev_space;                     /* 右键/空格边沿 */
    View views[MAX_VIEW]; int view_n;            /* 视图表 */
    u32 view_crc[MAX_VIEW];                      /* 子视图内容 CRC */
    Line lines[MAX_LINE]; int line_n;            /* 行布局 */
    Vector2 anchor[MAX_VIEW][512]; int anchor_n[MAX_VIEW];   /* token 锚点 */
    char cands[MAX_CAND][64]; int cand_prio[MAX_CAND]; int cand_n; int cand_ready; /* 补全候选 */
    Toks tmp_toks;                               /* 临时 fetched（free_fetched 用） */
    float tmp_ox, tmp_oy, tmp_ow;                /* 临时输出（pointer_locate/find_item_rect） */
    uint8_t tmp[2048];                           /* 临时缓冲（字符串等） */
} EState;

/* 状态偏移（供 gen_editor.py 生成器引用；C 侧直接用字段名） */
#define OFF_CAMERA       0
#define OFF_MOUSE_WORLD  (OFF_CAMERA + sizeof(Camera2D))
#define OFF_PTR_POS      (OFF_MOUSE_WORLD + sizeof(Vector2))
#define OFF_HAS_PTR      (OFF_PTR_POS + sizeof(Vector2))
#define OFF_CUR_V        (OFF_HAS_PTR + 4)
#define OFF_EDIT_V       (OFF_CUR_V + 4)
#define OFF_EDIT_I       (OFF_EDIT_V + 4)
#define OFF_EDIT_BUF     (OFF_EDIT_I + 4)
#define OFF_EDIT_LEN     (OFF_EDIT_BUF + 256)
#define OFF_INPUT_STR    (OFF_EDIT_LEN + 4)
#define OFF_INPUT_LEN    (OFF_INPUT_STR + 256)
#define OFF_COMPLETION   (OFF_INPUT_LEN + 4)
#define OFF_PRESSED_COMBO (OFF_COMPLETION + 128)
#define OFF_PREV_ALTL    (OFF_PRESSED_COMBO + 4)
#define OFF_PREV_ALTR    (OFF_PREV_ALTL + 4)
#define OFF_PREV_CTRL    (OFF_PREV_ALTR + 4)
#define OFF_PREV_SHIFT   (OFF_PREV_CTRL + 4)
#define OFF_SEL_START    (OFF_PREV_SHIFT + 4)
#define OFF_DEL_START    (OFF_SEL_START + 4)
#define OFF_COPY_BUF     (OFF_DEL_START + 4)
#define OFF_COPY_N       (OFF_COPY_BUF + 256 * sizeof(Tok))
#define OFF_DRAG_SV      (OFF_COPY_N + 4)
#define OFF_LDRAG        (OFF_DRAG_SV + 4)
#define OFF_LDRAG_OFF    (OFF_LDRAG + 4)
#define OFF_PREV_RB      (OFF_LDRAG_OFF + sizeof(Vector2))
#define OFF_PREV_SPACE   (OFF_PREV_RB + 4)
#define OFF_VIEWS        (OFF_PREV_SPACE + 4)
#define OFF_VIEW_N       (OFF_VIEWS + MAX_VIEW * sizeof(View))
#define OFF_VIEW_CRC     (OFF_VIEW_N + 4)
#define OFF_LINES        (OFF_VIEW_CRC + MAX_VIEW * 4)
#define OFF_LINE_N       (OFF_LINES + MAX_LINE * sizeof(Line))
#define OFF_ANCHOR       (OFF_LINE_N + 4)
#define OFF_ANCHOR_N     (OFF_ANCHOR + MAX_VIEW * 512 * sizeof(Vector2))
#define OFF_CANDS        (OFF_ANCHOR_N + MAX_VIEW * 4)
#define OFF_CAND_PRIO    (OFF_CANDS + MAX_CAND * 64)
#define OFF_CAND_N       (OFF_CAND_PRIO + MAX_CAND * 4)
#define OFF_CAND_READY   (OFF_CAND_N + 4)
#define OFF_TMP_TOKS     (OFF_CAND_READY + 4)
#define OFF_TMP_OX       (OFF_TMP_TOKS + sizeof(Toks))
#define OFF_TMP_OY       (OFF_TMP_OX + 4)
#define OFF_TMP_OW       (OFF_TMP_OY + 4)
#define OFF_TMP          (OFF_TMP_OW + 4)
#endif
