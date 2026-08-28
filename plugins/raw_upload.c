/* token="raw_upload" -> raw-ptr-editor：脏块上传并清脏 */
#include "plug_api.h"
__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    u32 klen = pop_u32(B);
    const uint8_t *key = (const uint8_t*)pop_ptr(B);
    B->raw_upload(key, klen);
    B->run_next();
}
