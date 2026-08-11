#include "simply.h"
#include <stdlib.h>
#include <string.h>

#include <stdio.h>
__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    const uint8_t *pay; u32 plen; B->cur_payload(&pay, &plen);
    uint32_t v = (uint32_t)strtoul((const char*)pay, NULL, 10);
    B->push((uint8_t*)&v, 4);
    B->write_num(4);
    B->run_next();
}
