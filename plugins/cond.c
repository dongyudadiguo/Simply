#include "simply.h"
#include <stdlib.h>
#include <string.h>

__declspec(dllexport) void run(void) {
    if (stk_off > 0 && stk[0] != 0 && plen) drill((data){plen, payload});
    else run_next();
}
