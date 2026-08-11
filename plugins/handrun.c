#include "simply.h"
#include <stdlib.h>
#include <string.h>

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    const uint8_t *pay; u32 plen; B->cur_payload(&pay, &plen);
    if (plen >= 8) {
        uint8_t b1, b2;
        B->hand_get(pay, &b1, &b2);
        if (b1) { B->hand_set(pay, 0, b2); B->drill((data){plen - 8, pay + 8}); }
        else if (b2) { B->drill((data){plen - 8, pay + 8}); }
        else B->run_next();
    } else B->run_next();
}
