
int fact(int n, int acc) {
    if (n <= 1) return acc;
    return fact(n - 1, acc * n);   /* Î²µİ¹é£º´«ÀÛ¼ÓÆ÷ */
}
