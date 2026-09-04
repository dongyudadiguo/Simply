#include "plug_api.h"

__declspec(dllexport) void run(void) {
    data payload = read_payload();
    var_unit* var = find_or_add_var(&global_var, &global_var_count, payload);
    if (var->data.ptr && var->data.size) {
        memcpy(stk_off, var->data.ptr, var->data.size);
        stk_off = (char*)stk_off + var->data.size;
        write_num(var->data.size);
    }
    run_next();
}
