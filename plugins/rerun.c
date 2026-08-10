#include "api.h"
#include <stdlib.h>
#include <string.h>

void rerun_run(const uint8_t *payload, uint32_t plen) {
    (void)payload; (void)plen;
    reset();
}
