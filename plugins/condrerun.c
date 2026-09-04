#include "plug_api.h"

__declspec(dllexport) void run(void) {
    data cond_val = read_stk();
    int v = 0;
    if (cond_val.size >= 4) v = *(int*)cond_val.ptr;
    else if (cond_val.size > 0) v = *(uint8_t*)cond_val.ptr;
    if (v != 0) {
        rerun();
    } else {
        run_next();
    }
}
