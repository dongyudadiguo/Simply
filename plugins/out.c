#include "simply.h"
#include <stdlib.h>
#include <string.h>

#include <stdio.h>
__declspec(dllexport) void run(void) {
    const uint8_t *pay; u32 plen; cur_payload(&pay, &plen);
    if (plen) { fwrite(pay, 1, plen, stdout); }
    else if (stk_off >= 4) { uint32_t v; memcpy(&v, stk + stk_off - 4, 4); printf("%u", v); }
    fflush(stdout);
    run_next();
}
