// server.c —— 内存库（对齐 server.py）：op1 投票 / op2 取 / op3 覆盖上传；每连接单操作
#include <winsock2.h>
#include <stdint.h>
#include <ws2tcpip.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <process.h>
#pragma comment(lib, "ws2_32.lib")

#define HOST "0.0.0.0"
#define PORT 8000

typedef struct Item { uint32_t votes; uint8_t *payload; uint32_t plen; struct Item *next; } Item;
typedef struct KeyEnt { uint8_t *key; uint32_t klen; Item *items; struct KeyEnt *next; } KeyEnt;
static KeyEnt *db = NULL;
static CRITICAL_SECTION lock;

static KeyEnt *find_key(const uint8_t *key, uint32_t klen) {
    KeyEnt *e = db;
    while (e) { if (e->klen == klen && memcmp(e->key, key, klen) == 0) return e; e = e->next; }
    return NULL;
}
static void store(const uint8_t *key, uint32_t klen, const uint8_t *data, uint32_t dlen) {
    KeyEnt *e = find_key(key, klen);
    if (!e) {
        e = (KeyEnt*)calloc(1, sizeof(KeyEnt));
        e->key = (uint8_t*)malloc(klen); memcpy(e->key, key, klen); e->klen = klen;
        e->next = db; db = e;
    }
    Item *it;
    while ((it = e->items)) { e->items = it->next; free(it->payload); free(it); }  /* 覆盖同 key */
    it = (Item*)calloc(1, sizeof(Item));
    it->payload = (uint8_t*)malloc(dlen); memcpy(it->payload, data, dlen); it->plen = dlen;
    e->items = it;
}

static int recv_exact(SOCKET s, uint8_t *buf, uint32_t n) {
    uint32_t got = 0;
    while (got < n) {
        int r = recv(s, (char*)buf + got, n - got, 0);
        if (r <= 0) return 0;
        got += (uint32_t)r;
    }
    return 1;
}
static int send_exact(SOCKET s, const uint8_t *buf, uint32_t n) {
    uint32_t sent = 0;
    while (sent < n) {
        int r = send(s, (const char*)buf + sent, n - sent, 0);
        if (r <= 0) return 0;
        sent += (uint32_t)r;
    }
    return 1;
}

static void handle(SOCKET c) {
    uint8_t op; uint32_t klen;
    if (!recv_exact(c, &op, 1) || !recv_exact(c, (uint8_t*)&klen, 4)) { closesocket(c); return; }
    uint8_t *key = (uint8_t*)malloc(klen);
    if (!recv_exact(c, key, klen)) { free(key); closesocket(c); return; }

    if (op == 1) {                       /* 投票：[1][key][4B idx] */
        uint32_t idx; recv_exact(c, (uint8_t*)&idx, 4);
        EnterCriticalSection(&lock);
        uint32_t votes = 0;
        KeyEnt *e = find_key(key, klen);
        if (e) { Item *it = e->items; uint32_t k = 0;
            while (it && k < idx) { it = it->next; k++; }
            if (it) { it->votes++; votes = it->votes; } }
        LeaveCriticalSection(&lock);
        send_exact(c, (uint8_t*)&votes, 4);
    }
    else if (op == 2) {                  /* 获取：[2][key] → 票数最高（最早插入）payload */
        EnterCriticalSection(&lock);
        uint32_t plen = 0; const uint8_t *payload = NULL;
        KeyEnt *e = find_key(key, klen);
        if (e) { Item *best = e->items;
            for (Item *it = e->items; it; it = it->next) if (it->votes > best->votes) best = it;
            payload = best->payload; plen = best->plen; }
        LeaveCriticalSection(&lock);
        if (e && payload) { send_exact(c, (uint8_t*)&plen, 4); send_exact(c, payload, plen); }
        /* 无数据：不发响应直接关（对齐 Python） */
    }
    else if (op == 3) {                  /* 上传：[3][key][plen][payload] → 覆盖 */
        uint32_t dlen; uint8_t *data = NULL;
        if (recv_exact(c, (uint8_t*)&dlen, 4)) {
            data = (uint8_t*)malloc(dlen);
            if (recv_exact(c, data, dlen)) {
                EnterCriticalSection(&lock);
                store(key, klen, data, dlen);
                LeaveCriticalSection(&lock);
            }
        }
        uint32_t zero = 0; send_exact(c, (uint8_t*)&zero, 4);
        free(data);
    }
    free(key);
    closesocket(c);
}

static unsigned __stdcall conn(void *p) { handle((SOCKET)(intptr_t)p); return 0; }

int main(void) {
    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) return 1;
    InitializeCriticalSection(&lock);
    SOCKET ls = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in a;
    a.sin_family = AF_INET; a.sin_port = htons(PORT); a.sin_addr.s_addr = INADDR_ANY;
    bind(ls, (struct sockaddr*)&a, sizeof a);
    listen(ls, 8);
    printf("server on %s:%d\n", HOST, PORT); fflush(stdout);
    for (;;) {
        SOCKET c = accept(ls, NULL, NULL);
        if (c == INVALID_SOCKET) continue;
        _beginthreadex(NULL, 0, conn, (void*)(intptr_t)c, 0, NULL);
    }
}
