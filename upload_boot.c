// upload_boot.c —— 上传编辑器块（editor_blocks.h 由 gen_editor.py 生成）
// 空 key 块 = 编辑器主循环 token 流；子块（ei/quit/bin/...）= 复用块（无 DLL 的 token 名 → 下钻）
#include "simply.h"
#include "editor_blocks.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void) {
    net_init();
    for (size_t i = 0; i < EDITOR_BLOCKS_N; i++) {
        const char *key = EDITOR_BLOCKS[i].key;
        uint32_t klen = EDITOR_BLOCKS[i].klen;
        int rc = net_upload((const uint8_t*)key, klen, EDITOR_BLOCKS[i].data, EDITOR_BLOCKS[i].len);
        printf("upload %-8s %4u bytes rc=%d\n", klen ? key : "(empty)", EDITOR_BLOCKS[i].len, rc);
    }
    return 0;
}
