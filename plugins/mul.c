#include "simply.h"
#include <stdlib.h>
#include <string.h>

void mul_run(const uint8_t *payload, uint32_t plen) {
    (void)payload; (void)plen;
    uint32_t o = stk_off;
    uint32_t a, b; memcpy(&a, stk + o - 8, 4); memcpy(&b, stk + o - 4, 4);
    uint32_t r = a * b;
    memcpy(stk + o - 8, &r, 4);
    stk_off = o - 4;
    write_num(4);
    run_next();
}
