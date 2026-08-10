
void abc(int n) {
    if (n <= 0) return;
    abc(n - 1);   /* 尾调用：是函数里最后做的事 */
}
