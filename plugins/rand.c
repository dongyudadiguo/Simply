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
} BlockAPI;
extern void *GetModuleHandleA(const char *name);
extern void *GetProcAddress(void *module, const char *name);
static inline BlockAPI *block_import(void) {
    typedef BlockAPI *(*fn)(void);
    return ((fn)GetProcAddress(GetModuleHandleA("block.dll"), "block_api"))();
}
#include <stdlib.h>
#include <string.h>

#include <stdio.h>
__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    int lo = 1, hi = 100;
    const uint8_t *pay; u32 plen; B->cur_payload(&pay, &plen);
    if (plen) { char buf[64]; uint32_t n = plen < 63 ? plen : 63;
        memcpy(buf, pay, n); buf[n] = 0;
        int a = 0, b = 0; int cnt = sscanf(buf, "%d %d", &a, &b);
        if (cnt > 0) lo = a; if (cnt > 1) hi = b;
    }
    uint32_t v = (uint32_t)(lo + (hi > lo ? rand() % (hi - lo + 1) : 0));
    B->push((uint8_t*)&v, 4);
    B->write_num(4);
    B->run_next();
}
