#include "simply.h"
#include <stdlib.h>
#include <string.h>

#include <stdio.h>
__declspec(dllexport) void run(void) {
    const uint8_t *pay; u32 plen; cur_payload(&pay, &plen);
    uint32_t v = (uint32_t)strtoul((const char*)pay, NULL, 10);
    push((uint8_t*)&v, 4);
    write_num(4);
    run_next();
}
