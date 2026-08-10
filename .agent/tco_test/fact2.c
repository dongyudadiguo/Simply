
int factorial2(int n) {
    if (n <= 1) return 1;
    return n * factorial2(n - 1);
}
