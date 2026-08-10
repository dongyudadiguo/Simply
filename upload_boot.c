// upload_boot.c —— 上传空 key 引导块 = [boot] + 全部插件 sha256 名（payload 空）
#include "api.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const char *NAMES[] = {
    "boot", "editor", "rerun", "add", "read", "set", "cond", "handrun", "condrerun",
    "push_int", "in-int", "out", "rand", "gt", "lt", "eq", "mul", "ret_int"
};
#define NAMES_N (sizeof(NAMES)/sizeof(NAMES[0]))

int main(void) {
    net_init();
    uint8_t block[4096]; uint32_t off = 0;
    for (size_t i = 0; i < NAMES_N; i++) {
        uint32_t nl = (uint32_t)strlen(NAMES[i]);
        memcpy(block + off, &nl, 4); off += 4;
        memcpy(block + off, NAMES[i], nl); off += nl;
        uint32_t z = 0; memcpy(block + off, &z, 4); off += 4;   /* payload 空 */
    }
    uint32_t z = 0; memcpy(block + off, &z, 4); off += 4;       /* 块结束 */
    int rc = net_upload((const uint8_t*)"", 0, block, off);
    printf("上传空 key 引导块: %d 字节, %zu token, rc=%d\n", off, NAMES_N, rc);
    return 0;
}
