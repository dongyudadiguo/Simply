#include "simply.h"
#include <stdlib.h>
#include <string.h>

#include <stdio.h>
void in_int_run(const uint8_t *payload, uint32_t plen) {
    (void)payload; (void)plen;
    int v; if (scanf("%d", &v) != 1) v = 0;
    uint32_t u = (uint32_t)v;
    push((uint8_t*)&u, 4);
    write_num(4);
    run_next();
}
