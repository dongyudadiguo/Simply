#include "simply.h"
#include <stdlib.h>
#include <string.h>

__declspec(dllexport) void run(void) {
    const uint8_t *pay; u32 plen; cur_payload(&pay, &plen);
    uint32_t v = var_off;
    while (v > 0) {
        uint32_t nsize, vsize; uint64_t vptr;
        memcpy(&nsize, var + v - 16, 4);
        memcpy(&vptr, var + v - 12, 8);
        memcpy(&vsize, var + v - 4, 4);
        if (nsize == plen && memcmp(var + v - 16 - nsize, pay, plen) == 0) {
            push(stk + (size_t)vptr, vsize);
            break;
        }
        v -= 16 + nsize;
    }
    run_next();
}
