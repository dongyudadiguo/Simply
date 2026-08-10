
__attribute__((musttail))
int foo(int n) {
    if (n <= 1) return 1;
    return n + foo(n - 1);  // 非尾调用，musttail 应报错
}
