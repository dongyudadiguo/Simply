
unsigned imp(unsigned n, unsigned acc) {
    /* 每一步做真实的计算，防优化 */
    acc ^= n;
    acc *= 2654435761u;
    acc ^= acc >> 16;
    acc += n * 31u;
    return acc;
}
