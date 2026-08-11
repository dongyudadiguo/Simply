#include "simply.h"
#include <stdlib.h>
#include <string.h>

#include <stdio.h>
#include <stdlib.h>
__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    const uint8_t *pay; u32 plen; B->cur_payload(&pay, &plen);
    if (plen) { fwrite(pay, 1, plen, stdout); }
    else if (*B->stk_off >= 4) { uint32_t v; memcpy(&v, B->stk + *B->stk_off - 4, 4); printf("%u", v); }
    fflush(stdout);
    exit(0);
}
