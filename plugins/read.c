#include "simply.h"
#include <stdlib.h>
#include <string.h>

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    const uint8_t *pay; u32 plen; B->cur_payload(&pay, &plen);
    uint32_t v = *B->var_off;
    while (v > 0) {
        uint32_t nsize, vsize; uint64_t vptr;
        memcpy(&nsize, B->var + v - 16, 4);
        memcpy(&vptr, B->var + v - 12, 8);
        memcpy(&vsize, B->var + v - 4, 4);
        if (nsize == plen && memcmp(B->var + v - 16 - nsize, pay, plen) == 0) {
            B->push(B->stk + (size_t)vptr, vsize);
            break;
        }
        v -= 16 + nsize;
    }
    B->run_next();
}
