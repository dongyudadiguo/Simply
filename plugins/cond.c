#include "simply.h"
#include <stdlib.h>
#include <string.h>

__declspec(dllexport) void run(void) {
    const uint8_t *pay; u32 plen; cur_payload(&pay, &plen);
    if (stk_off > 0 && stk[0] != 0 && plen) drill((data){plen, pay});
    else run_next();
}
