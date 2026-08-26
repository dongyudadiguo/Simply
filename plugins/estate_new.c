/* token="estate_new" -> sha256 -> <sha256(estate_new)>.dll（编辑器状态 EState + editor_lib 实现） */
#include "plug_api.h"
#include "editor_lib.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    EState *e = (EState*)calloc(1, sizeof(EState));   /* 编辑器状态：一次分配，指针存全局变量 */
    const uint8_t *d; u32 n;
    B->cur_root_of(&d, &n);                            /* 根块 key（id）= 根视图 key */
    u32 kl = n < 256 ? n : 256;
    if (d) memcpy(e->views[0].key, d, kl);
    e->views[0].klen = kl;
    e->views[0].pos = (Vector2){40, 60};
    e->views[0].src_v = -1; e->views[0].src_i = -1;
    e->view_n = 1;
    size_t cn = 0;
    if (!B->cur_get(e->views[0].key, e->views[0].klen, &cn)) {
        Toks ts = B->load_toks(e->views[0].key, e->views[0].klen);
        if (ts.n > 0) { B->cur_set(e->views[0].key, e->views[0].klen, ts.tok, ts.n); }
    }
    uint8_t *p = (uint8_t*)&e;                         /* 存指针本身 */
    B->gv_set((const uint8_t*)"estate", 6, p, 8);
    B->run_next();
}

