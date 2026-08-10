
#include <stdio.h>
int factorial(int n, int acc) {
    if (n <= 1) return acc;
    return factorial(n - 1, acc * n);
}
int main() {
    printf("factorial(1000000, 1) = %d\n", factorial(1000000, 1));
    return 0;
}
