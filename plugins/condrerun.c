#include "simply.h"
#include <stdlib.h>
#include <string.h>

void condrerun_run(const uint8_t *payload, uint32_t plen) {
    (void)payload; (void)plen;
    if (stk_off > 0 && stk[0] != 0) reset();
    else run_next();
}
