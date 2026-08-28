/* token="raw_mark" -> raw-ptr-editor：原地修改后标脏 */
#include "plug_api.h"
__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    u32 klen = pop_u32(B);
    const uint8_t *key = (const uint8_t*)pop_ptr(B);
    B->raw_mark(key, klen);
    B->run_next();
}
