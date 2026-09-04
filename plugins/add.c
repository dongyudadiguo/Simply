#include "plug_api.h"

__declspec(dllexport) void run(void) {
    num_off = 0;
    num_count = 0;
    stk_off = stk;
    *(int*)stk = *(int*)stk + *(int*)((char*)stk + 4);
    stk_off = (char*)stk + 4;
    write_num(4);
    run_next();
}
