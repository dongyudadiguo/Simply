/* token="raw_set" -> raw-ptr-editor：原始块字节整块写入并标脏 */
#include "plug_api.h"
__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    u32 dlen = pop_u32(B);
    const uint8_t *data = (const uint8_t*)pop_ptr(B);
    u32 klen = pop_u32(B);
    const uint8_t *key = (const uint8_t*)pop_ptr(B);
    B->raw_set(key, klen, data, dlen);
    B->run_next();
}
