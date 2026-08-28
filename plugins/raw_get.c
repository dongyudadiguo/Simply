/* token="raw_get" -> raw-ptr-editor：原始块字节读取 */
#include "plug_api.h"
__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    u32 klen = pop_u32(B);
    const uint8_t *key = (const uint8_t*)pop_ptr(B);
    const uint8_t *p; u32 n = 0;
    p = B->raw_get(key, klen, &n);
    push_ptr(B, p);
    push_u32(B, n);
    B->run_next();
}
