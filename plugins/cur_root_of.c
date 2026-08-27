/* token="cur_root_of" -> 当前根块 key 原语（块内零封壳初始化需要） */
#include "plug_api.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    const uint8_t *d = NULL;
    u32 n = 0;
    B->cur_root_of(&d, &n);
    push_ptr(B, d);
    push_u32(B, n);
    B->run_next();
}
