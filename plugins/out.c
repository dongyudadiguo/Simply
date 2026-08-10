#include "simply.h"
#include <stdlib.h>
#include <string.h>

#include <stdio.h>
void out_run(void) {
    if (plen) { fwrite(payload, 1, plen, stdout); }
    else if (stk_off >= 4) { uint32_t v; memcpy(&v, stk + stk_off - 4, 4); printf("%u", v); }
    fflush(stdout);
    run_next();
}
