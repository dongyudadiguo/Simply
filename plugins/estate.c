/* token="estate" -> sha256 -> <sha256(estate)>.dll（全局变量 "estate" 里的 EState 指针，解引用后压栈） */
#include "plug_api.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    u32 n = 0;
    const uint8_t *d = B->gv_get((const uint8_t*)"estate", 6, &n);
    void *p = NULL;
    if (d && n >= 8) memcpy(&p, d, 8);               /* 存储的是指针值本身 */
    push_ptr(B, p);
    B->run_next();
}
