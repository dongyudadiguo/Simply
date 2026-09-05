#include "plug_api.h"

__declspec(dllexport) void run(void) {
    off_reset();
    data payload = read_payload();
    if(*(char*)stk) {
        (*(u32*)payload.ptr)++;
        rerun();
    }
    run_next();
}
