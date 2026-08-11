#include "simply.h"
#include <stdlib.h>
#include <string.h>

__declspec(dllexport) void run(void) {
    BlockAPI *B = block_import();
    if (*B->stk_off > 0 && B->stk[0] != 0) B->reset();
    else B->run_next();
}
