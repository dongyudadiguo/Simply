#include "plug_api.h"

__declspec(dllexport) void run(void) {
    data payload = read_payload();
    var_unit* var = find_or_add_var(&local_var, &local_var_count, payload);
    memcpy(stk_off, var->data.ptr, var->data.size);
    Add_size(var->data.size);
    run_next();
}
