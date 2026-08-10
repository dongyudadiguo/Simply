#include "simply.h"
#include <stdlib.h>
#include <string.h>

void cond_run(void) {
    if (stk_off > 0 && stk[0] != 0 && plen) run_block(payload, plen);
    else run_next();
}
