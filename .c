#define WIN32_LEAN_AND_MEAN
#define NOGDI
#define NOUSER
#include <winsock2.h>
#include "raylib.h"
#include "raymath.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <math.h>

typedef uint32_t u32;
typedef uint64_t u64;
typedef struct { void *d; unsigned n; } data;
typedef struct data_map {
    data key;
    struct data_map *datas;
    u32 data_count;
} data_map;
typedef struct strs {
    char **str;
    int index;
} strs;
static data get_payload(data k) {
    WSADATA wsa;
    WSAStartup(MAKEWORD(2, 2), &wsa);
    SOCKET s = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in a = {0};
    a.sin_family = AF_INET;
    a.sin_port = htons(8000);
    a.sin_addr.s_addr = inet_addr("127.0.0.1");
    connect(s, (struct sockaddr *)&a, sizeof a);
    char op = 2;
    send(s, &op, 1, 0);
    send(s, (char *)&k.n, 4, 0);
    send(s, k.d, k.n, 0);
    unsigned n;
    if (recv(s, (char *)&n, 4, 0) <= 0) {
        closesocket(s);
        return (data){0, 0};
    }
    void *d = malloc(n);
    recv(s, d, n, 0);
    closesocket(s);
    return (data){d, n};
}

static data_map fetch_data_map(data k) {
    data_map m = {k, 0, 0};
    m.key.d = memcpy(malloc(k.n), k.d, k.n);
    data payload = get_payload(k);
    unsigned char *p = payload.d;
    u32 off = 0;
    while (payload.d && off + 4 <= payload.n) {
        u32 n;
        memcpy(&n, p + off, 4);
        off += 4;
        data child = {p + off, n};
        off += n;
        m.datas = realloc(m.datas, (m.data_count + 1) * sizeof(data_map));
        m.datas[m.data_count++] = fetch_data_map(child);
    }
    free(payload.d);
    return m;
}

data_map get_data_map(void) {
    return fetch_data_map((data){0, 0});
}

static void data_map_collect(data_map m, strs *out) {
    if (m.key.n) {
        char *s = malloc(m.key.n + 1);
        memcpy(s, m.key.d, m.key.n);
        s[m.key.n] = 0;
        out->str = realloc(out->str, (out->index + 1) * sizeof(char *));
        out->str[out->index++] = s;
    }
    for (u32 i = 0; i < m.data_count; i++)
        data_map_collect(m.datas[i], out);
}

strs data_map_to_strs(data_map m) {
    strs out = {0, 0};
    data_map_collect(m, &out);
    return out;
}

static int by_len(const void *a, const void *b) {
    return (int)strlen(*(char **)a) - (int)strlen(*(char **)b);
}

strs sort_strs(strs s) {
    qsort(s.str, s.index, sizeof(char *), by_len);
    return s;
}

char *find_str(strs index_strs, char *input_str) {
    char *final_str = "";
    for (int i = 0; i < index_strs.index; i++) {
        char *str = index_strs.str[i];
        if (strstr(str, input_str) == str)
            final_str = str;
        if (strcmp(str, input_str) == 0)
            return str;
    }
    return final_str;
}

typedef void (*imp_fn)(void);

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
#define block_size (1 << 16)

Camera2D camera;
Vector2 mouseWorldPos, pos, draw_pos, line_pos, offset, bg_pos;
Color drawcolor;
void *view, *point, *fixed_point, *base, *copy, *txt;
void *views[64];
Vector2 views_pos[64];
Vector2 func_pos[64];
void *funcs[64];
float end_y[64];
int max_x[64];
data views_key[64];
int view_index, view_index_current, draggingIndex;
int runonece, is_fun, is_point, is_right, fun_max, bracket;
int lastdrawwidth, next_line_y;
char input_str[256];
char *completion;
static strs all_strs;
char remove_underscores_buff[512];
int switch_buff;
data key;
FILE *file;
typedef struct
{
    data key;
    float heat;
} KeyHeat;
static KeyHeat keyheat[256];
static int key_heat_count;
typedef struct
{
    void *p;
    u32 heat;
} AddrHeat;
static AddrHeat adshet[256];
static int adshet_n;

void *get_global_variables(data k) { (void)k; return 0; }
void separate_payload_input(void *pay, void *txt) { (void)pay; (void)txt; }

data strkey(const char *s) { return (data){(void *)s, (unsigned)strlen(s)}; }
int keycmp(data a, data b) { return a.n == b.n && memcmp(a.d, b.d, a.n) == 0; }

int find_func(void *tmp) {
    for (int i = 0; i < fun_max; i++)
        if (funcs[i] == tmp) return i;
    return 0;
}

void change_ret(int size) { (void)size; }

void free_block_space(void *p, int size) {
    memmove((char *)p + size, p, block_size / 2);
}

void insert_str_token(char *s) {
    int n = (int)strlen(s);
    int sz = 4 + n + 4;
    free_block_space(point,sz);
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

void *next_payload(void *p) {
    return p + 4 + *(u32 *)p;
}

void *next_token(void *p) {
    unsigned char *q = p;
    q = next_payload(q);
    q = next_payload(q);
    return q;
}

void view_to_next_token(void) {
    view = next_token(view);
}

void next_token_is_set(void) {
    if(*(u32*)next_token(view) == 3 && memcmp(next_token(view) + 4, "set", 3) == 0) {
        offset = (Vector2){lastdrawwidth, 0};
    }
}
u32 find_or_add_address_heat(void *p, AddrHeat *tab)
{
    (void)tab;
    for (int i = 0; i < adshet_n; i++)
        if (adshet[i].p == p)
            return adshet[i].heat;
    adshet[adshet_n].p = p;
    adshet[adshet_n].heat = 1;
    adshet_n++;
    return 0;
}
u32 address_heat(void *p) {
    return *(u32 *)p - find_or_add_address_heat(p, adshet);
}
data address_data(void *p) { return (data){p, 4}; }
void set_key_heat(u32 h, data k)
{
    for (int i = 0; i < key_heat_count; i++)
        if (keycmp(keyheat[i].key, k))
        {
            keyheat[i].heat = (float)h;
            return;
        }
    keyheat[key_heat_count].key = (data){memcpy(malloc(k.n), k.d, k.n), k.n};
    keyheat[key_heat_count].heat = (float)h;
    key_heat_count++;
}
double brightness(uint32_t d, double h)
{
    double theta = atan2((double)d, h);
    return 0.1 + 0.9 * (theta / (M_PI / 2.0));
}
float get_key_heat(data key) {
    for (int i = 0; i < key_heat_count; i++) {
        if (keycmp(keyheat[i].key, key)) {
            return keyheat[i].heat;
        }
    }
    return 0;
}
static data u64_to_data(u64 x)
{
    static u64 box;
    box = x;
    return (data){&box, 8};
}
static void payload_input(void *pay)
{
    char *str = pay + 4;
    if (IsKeyPressed(KEY_BACKSPACE)) {
        int n = *(u32 *)pay;
        if (n) str[n - 1] = '\0';
    }
    int k = GetCharPressed();
    if (k) {
        char *add_char = pay + 4 + *(u32 *)pay;
        free_block_space(add_char, 1);
        add_char[0] = (char)k;
        *(u32 *)pay += 1;
    }
    
}
static Vector2 MouseDelta_zoom(void)
{
    return Vector2Scale(GetMouseDelta(), 1.0f / (camera.zoom ? camera.zoom : 1.0f));
}
void draw_view(void) {
    float key_heat = get_key_heat(views_key[view_index_current]);
    if(key_heat) {
        DrawRectangle(pos.x, pos.y, max_x[view_index_current], 20, Fade(WHITE, brightness(key_heat, 100)));
    }
    while (1) {
        key = (data){(char *)view + 4, *(u32 *)view};
        if (*(int*)key.d == -1)
        {
            end_y[view_index_current] = pos.y;
            return;
        }
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
        offset = (Vector2){0, 20};
        
        if (keycmp(key, strkey("get"))) {
            offset = (Vector2){lastdrawwidth, 0};
            payload_input(next_payload(view));
            txt = next_payload(view) + 4;
            drawcolor = SKYBLUE;
        } else if (keycmp(key, strkey("set"))) {
            next_token_is_set();
            payload_input(next_payload(view));
            txt = next_payload(view) + 4;
            drawcolor = SKYBLUE;
        } else if (keycmp(key, strkey("handrun"))) {
            next_token_is_set();
            if(IsMouseButtonPressed(MOUSE_BUTTON_LEFT)) {
                *(char*)get_global_variables(u64_to_data(*(u64*)(next_payload(view) + 4))) = 1;
            }
            if(IsMouseButtonPressed(MOUSE_BUTTON_RIGHT)) {
                char* tmp = (char*)get_global_variables(u64_to_data(*(u64*)(next_payload(view) + 4))) + 1;
                *tmp = !*tmp;
            }
            separate_payload_input(next_payload(view), txt = next_payload(view) + 4 + 8);
            drawcolor = BROWN;
        } else if (keycmp(key, strkey("cond"))) {
            next_token_is_set();
            set_key_heat(address_heat(next_payload(view) + 4), (data){next_payload(view) + 12, *(u32*)(next_payload(view) + 8)});
            separate_payload_input(next_payload(view),next_payload(view) + 4);
            txt = next_payload(view) + 4 + 4;
            drawcolor = LIGHTGRAY;
        } else if (keycmp(key, strkey("condrerun"))) {
            next_token_is_set();
            set_key_heat(address_heat(next_payload(view) + 4), (data){next_payload(view) + 12, *(u32*)(next_payload(view) + 8)});
            separate_payload_input(next_payload(view),next_payload(view) + 4);
            txt = next_payload(view) + 4 + 4;
            drawcolor = GRAY;
        }
        pos.x += offset.x;
        pos.y += offset.y;
        draw_pos = pos;
        lastdrawwidth = MeasureText(txt, 20);
        max_x[view_index_current] = max(max_x[view_index_current], lastdrawwidth);
        if (IsMouseButtonPressed(MOUSE_BUTTON_RIGHT) && CheckCollisionPointRec(mouseWorldPos, (Rectangle){draw_pos.x, draw_pos.y, (float)lastdrawwidth, 20})) {
            draggingIndex = view_index_current;
            views[view_index] = data_to_data(key).d;
            views_pos[view_index] = mouseWorldPos;
            views_key[view_index] = key;
            draggingIndex = view_index;
            view_index++;
        }
        is_right = 0;
        if (CheckCollisionPointRec(mouseWorldPos, (Rectangle){draw_pos.x + lastdrawwidth, draw_pos.y, 120, 20})) {
            point = next_token(point);
            line_pos.x += (float)lastdrawwidth;
            is_right = 1;
        }
        DrawText(txt, (int)draw_pos.x, (int)draw_pos.y, 20, drawcolor);
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
        all_strs = sort_strs(data_map_to_strs(get_data_map()));
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
        insert_str_token(is_right ? "set" : "get");
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
    completion = find_str(all_strs, input_str);
    DrawText(TextFormat("%s %s", input_str, completion), GetMouseX() + 20, GetMouseY(), 20, WHITE);
    EndDrawing();
    set_ptr(base);
    {
        const uint8_t *p = get_ptr();
        drill((data){(void *)(p + 4), *(u32 *)p});
    }
}
