/* token="drop" -> sha256 -> <sha256(drop)>.dll（plug_api.h 结构） */
#include "plug_api.h"

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    pop_u32(B);                                  /* 丢弃栈顶 4 字节 */
    B->run_next();
}

