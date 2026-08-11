#include "simply.h"
#include <stdlib.h>
#include <string.h>

#include <stdio.h>
__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    int v; if (scanf("%d", &v) != 1) v = 0;
    uint32_t u = (uint32_t)v;
    B->push((uint8_t*)&u, 4);
    B->write_num(4);
    B->run_next();
}
