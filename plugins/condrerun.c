#include "simply.h"
#include <stdlib.h>
#include <string.h>

void condrerun_run(void) {
    if (stk_off > 0 && stk[0] != 0) reset();
    else run_next();
}
