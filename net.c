// net.c —— 裸 TCP 客户端（对齐 Python block.py 的 fetch/upload）
#include <winsock2.h>
#include <ws2tcpip.h>
#include "simply.h"
#include <stdlib.h>
#include <string.h>
#pragma comment(lib, "ws2_32.lib")

static int inited = 0;
int net_init(void) {
    if (inited) return 0;
    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) return -1;
    inited = 1;
    return 0;
}

static SOCKET connect_vm(void) {
    SOCKET s = socket(AF_INET, SOCK_STREAM, 0);
    if (s == INVALID_SOCKET) return INVALID_SOCKET;
    struct sockaddr_in a;
    a.sin_family = AF_INET;
    a.sin_port = htons(VM_PORT);
    inet_pton(AF_INET, "127.0.0.1", &a.sin_addr);
    if (connect(s, (struct sockaddr*)&a, sizeof a) != 0) { closesocket(s); return INVALID_SOCKET; }
    return s;
}

/* 精确读 n 字节到 buf（buf 需已有空间），成功返回 1 */
static int recv_exact(SOCKET s, uint8_t *buf, uint32_t n) {
    uint32_t got = 0;
    while (got < n) {
        int r = recv(s, (char*)buf + got, n - got, 0);
        if (r <= 0) return 0;
        got += (uint32_t)r;
    }
    return 1;
}

/* fetch：op=2，[2][klen][key] → 读 [plen][payload]；malloc，失败 NULL */
uint8_t *net_fetch(const uint8_t *key, uint32_t klen, uint32_t *out_len) {
    net_init();
    SOCKET s = connect_vm();
    if (s == INVALID_SOCKET) return NULL;
    uint8_t op = 2;
    uint8_t *req = (uint8_t*)malloc(5 + klen);
    req[0] = op; memcpy(req+1, &klen, 4); memcpy(req+5, key, klen);
    send(s, (const char*)req, 5 + klen, 0); free(req);
    uint32_t plen;
    if (!recv_exact(s, (uint8_t*)&plen, 4)) { closesocket(s); return NULL; }
    uint8_t *data = (uint8_t*)malloc(plen ? plen : 1);
    if (plen && !recv_exact(s, data, plen)) { closesocket(s); free(data); return NULL; }
    closesocket(s);
    if (out_len) *out_len = plen;
    return data;
}

/* upload：op=3，[3][klen][key][plen][payload] → 读 [4B idx]；成功返回 0 */
int net_upload(const uint8_t *key, uint32_t klen, const uint8_t *data, uint32_t dlen) {
    net_init();
    SOCKET s = connect_vm();
    if (s == INVALID_SOCKET) return -1;
    uint8_t *req = (uint8_t*)malloc(9 + klen + dlen);
    req[0] = 3; memcpy(req+1, &klen, 4); memcpy(req+5, key, klen);
    memcpy(req+5+klen, &dlen, 4); memcpy(req+9+klen, data, dlen);
    send(s, (const char*)req, 9 + klen + dlen, 0); free(req);
    uint32_t idx;
    int ok = recv_exact(s, (uint8_t*)&idx, 4);
    closesocket(s);
    return ok ? 0 : -1;
}
