#include "simply.h"
#include <stdlib.h>
#include <string.h>

__declspec(dllexport) void run(void) {
    const uint8_t *pay; u32 plen; cur_payload(&pay, &plen);
    if (plen >= 8) {
        uint8_t b1, b2;
        hand_get(pay, &b1, &b2);
        if (b1) { hand_set(pay, 0, b2); drill((data){plen - 8, pay + 8}); }
        else if (b2) { drill((data){plen - 8, pay + 8}); }
        else run_next();
    } else run_next();
}
