#include "api.h"
#include <stdlib.h>
#include <string.h>

void cond_run(const uint8_t *payload, uint32_t plen) {
    if (stk_off > 0 && stk[0] != 0 && plen) run_block(payload, plen);
    else run_next();
}
