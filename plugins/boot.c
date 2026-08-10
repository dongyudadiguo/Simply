#include "simply.h"
#include <stdlib.h>
#include <string.h>

#include <stdio.h>
void boot_run(void) {
    uint8_t id[32];
    FILE *f = fopen("id.bin", "rb");
    if (f) {
        if (fread(id, 1, 32, f) == 32) {
            uint32_t blen = 0;
            uint8_t *blk = net_fetch(id, 32, &blen);          /* server 有该块 → 直接用 */
            if (blk) { free(blk); run_block(id, 32); return; }
        }
        fclose(f);
    }
    for (int i = 0; i < 32; i++) id[i] = (uint8_t)(rand() & 0xff);   /* 生成新 id */
    f = fopen("id.bin", "wb"); fwrite(id, 1, 32, f); fclose(f);
    uint8_t block[31] = {                 /* 引导块 [editor][rerun] */
        6,0,0,0,'e','d','i','t','o','r',0,0,0,0,
        5,0,0,0,'r','e','r','u','n',0,0,0,0,
        0,0,0,0};
    net_upload(id, 32, block, 31);        /* 首次/恢复：上传引导块 */
    run_block(id, 32);
}
