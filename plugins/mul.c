#include "simply.h"
#include <stdlib.h>
#include <string.h>

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    uint32_t o = *B->stk_off;
    uint32_t a, b; memcpy(&a, B->stk + o - 8, 4); memcpy(&b, B->stk + o - 4, 4);
    uint32_t r = a * b;
    memcpy(B->stk + o - 8, &r, 4);
    *B->stk_off = o - 4;
    B->write_num(4);
    B->run_next();
}
