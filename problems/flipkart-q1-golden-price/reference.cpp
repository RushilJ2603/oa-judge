#include <iostream>
using namespace std;

static bool isGolden(int g) {
    int sum = 0, hi = 0;
    for (int t = g; t > 0; t /= 10) {
        int d = t % 10;
        sum += d;
        if (d > hi) hi = d;
    }
    return sum - hi == hi;          // digitSum == 2 * maxDigit
}

int totalAmount(int x, int y) {
    if (x > y) { int t = x; x = y; y = t; }
    long long total = 0;
    for (int g = x; g <= y; ++g)
        if (isGolden(g)) total += g;
    return (int)total;
}

int main() {
    int X, Y;
    cin >> X >> Y;
    cout << totalAmount(X, Y);
    return 0;
}
