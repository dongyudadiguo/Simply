#include "plug_api.h"

__declspec(dllexport) void run(void) {
    var_unit* var = find_or_add_var(&local_var, &local_var_count, read_payload());
    int size = num[num_off++];
    var->data = (data){stk, size};
    stk += size;
    run_next();
}
