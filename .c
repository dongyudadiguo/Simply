#include "raylib.h"
#include "raymath.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

typedef uint32_t u32;
typedef struct { void *d; unsigned n; } data;
typedef void (*imp_fn)(void);

extern void *GetModuleHandleA(const char *name);
extern void *GetProcAddress(void *module, const char *name);

static data data_to_data(data k) {
    typedef data (*fn)(data);
    return ((fn)GetProcAddress(GetModuleHandleA(0), "data_to_data"))(k);
}
static void drill(data k) {
    typedef void (*fn)(data);
    ((fn)GetProcAddress(GetModuleHandleA(0), "drill"))(k);
}
static const uint8_t *get_ptr(void) {
    return *(const uint8_t **)GetProcAddress(GetModuleHandleA(0), "ptr");
}
static void set_ptr(const uint8_t *p) {
    *(const uint8_t **)GetProcAddress(GetModuleHandleA(0), "ptr") = p;
}

#define u32max 0xFFFFFFFFu
#define block_size (1 << 20)

Camera2D camera;
Vector2 mouseWorldPos, pos, draw_pos, line_pos;
Color drawcolor;
void *view, *point, *fixed_point, *base, *copy, *txt;
void *views[64];
Vector2 views_pos[64];
Vector2 func_pos[64];
void *funcs[64];
float end_y[64];
int view_index, view_index_current, draggingIndex;
int runonece, is_fun, is_point, is_right, fun_max, bracket;
int lastdrawwight, next_line_y;
char input_str[256];
char completion[128];
char remove_underscores_buff[512];
int switch_buff;
data key;
FILE *file;

data strkey(const char *s) { return (data){(void *)s, (unsigned)strlen(s)}; }
int keycmp(data a, data b) { return a.n == b.n && memcmp(a.d, b.d, a.n) == 0; }

int find_func(void *tmp) {
    for (int i = 0; i < fun_max; i++)
        if (funcs[i] == tmp) return i;
    return 0;
}

void change_ret(int size) { (void)size; }

void insert_str_token(char *s) {
    int n = (int)strlen(s);
    int sz = 4 + n + 4;
    memmove((char *)point + sz, point, block_size / 2);
    memcpy(point, &n, 4);
    memcpy((char *)point + 4, s, n);
    int z = 0;
    memcpy((char *)point + 4 + n, &z, 4);
    point = (char *)point + sz;
    change_ret(sz);
}

void set_mouse_pos_next(int offset_x, int offset_y) {
    SetMousePosition(GetMouseX() + offset_x, GetWorldToScreen2D((Vector2){line_pos.x, (float)offset_y}, camera).y + 2);
}

void clean_input_str(void) {
    input_str[0] = '\0';
    GetCharPressed();
}

void key_end(void) {
    clean_input_str();
    set_mouse_pos_next(0, (int)line_pos.y + 20);
}

void *remove_underscores(char *str) {
    char *dst_buff = remove_underscores_buff + switch_buff * 256;
    char *dst = dst_buff;
    switch_buff = !switch_buff;
    while (*str) {
        if (*str != '_') {
            *dst = *str;
            dst++;
        }
        str++;
    }
    *dst = '\0';
    return dst_buff;
}

void input(char *s) {
    if (IsKeyPressed(KEY_BACKSPACE)) {
        int n = (int)strlen(s);
        if (n) s[n - 1] = '\0';
    }
    int k = GetCharPressed();
    if (k) {
        char c[2] = {(char)k, 0};
        strcat(s, c);
    }
}

void next_token(void **p) {
    unsigned char *q = *p;
    q += *(int *)q + (int)sizeof(int);
    q += *(int *)q + (int)sizeof(int);
    *p = q;
}

void view_to_next_token(void) {
    next_token(&view);
}

void draw_view(void) {
    while (1) {
        key = (data){(char *)view + 4, *(u32 *)view};
        drawcolor = WHITE;
        txt = key.d;
        if (mouseWorldPos.y >= pos.y && mouseWorldPos.y <= end_y[view_index_current] && mouseWorldPos.x >= pos.x) {
            point = view;
        }
        is_point = fixed_point == view;
        if (is_point) {
            line_pos = pos;
            if (IsKeyPressed(KEY_HOME)) {
                view_index = view_index_current + 1;
            }
        }
        if (next_line_y == 0 && view > fixed_point) {
            next_line_y = (int)pos.y;
        }
        if (keycmp(key, strkey("get"))) {
            drawcolor = SKYBLUE;
        } else if (keycmp(key, strkey("set"))) {
            drawcolor = SKYBLUE;
        } else if (keycmp(key, strkey("handrun"))) {
            drawcolor = BROWN;
        } else if (keycmp(key, strkey("cond"))) {
            drawcolor = LIGHTGRAY;
        } else if (keycmp(key, strkey("condrerun"))) {
            drawcolor = LIGHTGRAY;
        }
        draw_pos = pos;
        pos.y += 20;
        if (key.n == u32max) {
            end_y[view_index_current] = pos.y;
            return;
        }
        char label[128];
        unsigned n = key.n < 127 ? key.n : 127;
        memcpy(label, txt, n);
        label[n] = 0;
        lastdrawwight = MeasureText(label, 20);
        if (IsMouseButtonPressed(MOUSE_BUTTON_RIGHT) && CheckCollisionPointRec(mouseWorldPos, (Rectangle){draw_pos.x, draw_pos.y, (float)lastdrawwight, 20})) {
            draggingIndex = view_index_current;
            views[view_index] = data_to_data(key).d;
            views_pos[view_index] = mouseWorldPos;
            draggingIndex = view_index;
            view_index++;
        }
        is_right = 0;
        if (CheckCollisionPointRec(mouseWorldPos, (Rectangle){draw_pos.x + lastdrawwight, draw_pos.y, 120, 20})) {
            next_token(&point);
            line_pos.x += (float)lastdrawwight;
            is_right = 1;
        }
        DrawText(label, (int)draw_pos.x, (int)draw_pos.y, 20, drawcolor);
        view_to_next_token();
    }
}

__declspec(dllexport) void run(void) {
    if (!runonece) {
        if (file) fclose(file);
        SetConfigFlags(FLAG_WINDOW_RESIZABLE);
        InitWindow(640, 480, "SelfEdit");
        camera.zoom = 1.0f;
        views[view_index] = base = (void *)get_ptr();
        views_pos[view_index++] = (Vector2){0.0f, 0.0f};
        runonece = 1;
    }
    BeginDrawing();
    ClearBackground(BLACK);
    BeginMode2D(camera);
    is_fun = 0;
    if (IsKeyPressed(KEY_SPACE)) {
        insert_str_token(input_str);
        key_end();
    }
    if (IsKeyPressed(KEY_TAB)) {
        strcpy(input_str, remove_underscores(completion));
    }
    if (IsKeyPressed(KEY_LEFT_ALT)) {
        if (is_right) {
            insert_str_token("set");
        } else {
            insert_str_token("get");
        }
        key_end();
    }
    if (IsKeyPressed(KEY_DELETE)) {
        copy = point;
    }
    if (IsKeyReleased(KEY_DELETE)) {
        memmove(copy, point, block_size / 2);
        change_ret((int)((char *)point - (char *)copy));
    }
    static void *copy2[2];
    if (IsKeyPressed(KEY_LEFT_SHIFT)) {
        copy2[0] = point;
    }
    if (IsKeyReleased(KEY_LEFT_SHIFT)) {
        copy2[1] = point;
    }
    if (IsKeyPressed(KEY_INSERT)) {
        int size = (int)((char *)copy2[1] - (char *)copy2[0]);
        void *tmp = malloc(size);
        memcpy(tmp, copy2[0], size);
        memmove((char *)point + size, point, block_size / 2);
        memcpy(point, copy2[0], size);
        free(tmp);
    }
    if (IsKeyPressed(KEY_DOWN)) {
        set_mouse_pos_next(0, next_line_y);
    }
    if (WindowShouldClose()) {
        exit(0);
    }
    float wheel = GetMouseWheelMove();
    if (wheel != 0) {
        camera.zoom += wheel * (0.1f * camera.zoom);
    }
    camera.offset = (Vector2){(float)GetScreenWidth() / 2, (float)GetScreenHeight() / 2};
    mouseWorldPos = GetScreenToWorld2D(GetMousePosition(), camera);
    if (IsMouseButtonDown(MOUSE_BUTTON_MIDDLE)) {
        camera.target = Vector2Subtract(camera.target, MouseDelta_zoom());
    }
    if (IsMouseButtonDown(MOUSE_BUTTON_RIGHT)) {
        views_pos[draggingIndex] = Vector2Add(views_pos[draggingIndex], MouseDelta_zoom());
    }
    next_line_y = 0;
    for (view_index_current = 0; view_index_current < view_index; view_index_current++) {
        view = views[view_index_current];
        pos = views_pos[view_index_current];
        DrawLineV(func_pos[find_func(views[view_index_current])], pos, LIME);
        draw_view();
    }
    input(input_str);
    fixed_point = point;
    DrawLine((int)line_pos.x, (int)line_pos.y, (int)mouseWorldPos.x, (int)line_pos.y, GRAY);
    EndMode2D();
    const char *tmp = TextFormat("%s %s", input_str, completion);
    DrawText(tmp, GetMouseX() + 20, GetMouseY(), 20, WHITE);
    EndDrawing();
    set_ptr(base);
    {
        const uint8_t *p = get_ptr();
        drill((data){(void *)(p + 4), *(u32 *)p});
    }
}
