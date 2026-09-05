#include "plug_api.h"

__declspec(dllexport) void run(void) {
    data payload = read_payload();
    var_unit* var = find_or_add_var(&global_var, &global_var_count, payload);
    memcpy(stk_off, var->data.ptr, var->data.size);
    if (!var->data.size) {
        var->data = (data){calloc(1, 1), 1};
    }
    Add_size(var->data.size);
    run_next();
}
