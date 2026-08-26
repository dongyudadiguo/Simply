/* token="call" -> sha256 -> <sha256(call)>.dll（plug_api.h 结构） */
#include "plug_api.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    const uint8_t *pay; u32 plen; B->cur_payload(&pay, &plen);
    B->drill((data){plen, pay});                 /* 无条件调用目标块（drill 接棒，不 run_next） */
}

