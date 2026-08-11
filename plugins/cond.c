#include "simply.h"
#include <stdlib.h>
#include <string.h>

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    const uint8_t *pay; u32 plen; B->cur_payload(&pay, &plen);
    if (*B->stk_off > 0 && B->stk[0] != 0 && plen) B->drill((data){plen, pay});
    else B->run_next();
}
