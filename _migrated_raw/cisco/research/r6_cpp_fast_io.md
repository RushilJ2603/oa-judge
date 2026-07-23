# C++ Fast I/O and I/O Gotchas Reference

This guide covers essential performance optimizations and correctness traps for C++ Input/Output, especially useful for Online Assessments (OAs) and Competitive Programming.

## 1. `ios_base::sync_with_stdio(false)` and `cin.tie(nullptr)`

**What they do:**
- `ios_base::sync_with_stdio(false)`: Disables the synchronization between C (`stdio`) and C++ (`iostream`) standard streams. By default, they are synced so you can mix `printf` and `cout` safely. Disabling this makes C++ streams much faster.
- `cin.tie(nullptr)`: Unties `cin` from `cout`. By default, `cin` is tied to `cout`, meaning `cout` is automatically flushed before any read operation on `cin`. Untying them prevents unnecessary flushes.

**When they help:**
Whenever you are reading or writing a large amount of data using `cin` and `cout`.

**The Danger:**
After disabling synchronization, mixing C (`scanf`/`printf`) and C++ (`cin`/`cout`) I/O functions will result in interleaved and unpredictable output/input order.

**Compilable Snippet:**
```cpp
#include <iostream>

using namespace std;

int main() {
    // Fast I/O
    ios_base::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    if (cin >> n) {
        cout << "Read " << n << "\n";
    }

    // DANGER: Do not use scanf/printf here!
    // printf("This might appear out of order!\n"); 
    return 0;
}
```

## 2. Exhaustive `scanf`/`printf` Format Specifiers

When `cin`/`cout` are still too slow or complex formatting is needed, `scanf`/`printf` are extremely fast and versatile.

**Common Specifiers:**
- `%d`: `int`
- `%u`: `unsigned int`
- `%ld`: `long int`
- `%lld`: `long long int`
- `%f`: `float`
- `%lf`: `double`
- `%c`: `char`
- `%s`: C-string (`char[]`)

**Width and Precision:**
- `%5d`: Padded with spaces to 5 characters wide.
- `%05d`: Padded with zeros to 5 characters wide.
- `%.2f`: Prints a float/double with 2 decimal places.

**Compilable Snippet:**
```cpp
#include <cstdio>

int main() {
    int i = 42;
    unsigned int ui = 42;
    long int li = 424242;
    long long int lli = 424242424242LL;
    float f = 3.14159f;
    double d = 3.1415926535;
    char c = 'A';
    char s[] = "Cisco";

    printf("int: %d\n", i);
    printf("unsigned int: %u\n", ui);
    printf("long int: %ld\n", li);
    printf("long long int: %lld\n", lli);
    printf("float: %f\n", f);
    printf("double: %lf\n", d); // %f also works for printing doubles in printf
    printf("char: %c\n", c);
    printf("string: %s\n", s);

    // Width & Precision
    printf("Padded int: %05d\n", i);
    printf("Precision double: %.2lf\n", d);

    return 0;
}
```

## 3. Printing Without `endl`

**Why `endl` is slow:**
`std::endl` not only inserts a newline character (`\n`) but also flushes the output buffer. Flushing is an expensive OS-level operation. Doing this in a loop can drastically increase execution time.

**The Fix:**
Always use `'\n'` or `"\n"` instead of `endl` when printing large amounts of data.

**Compilable Snippet:**
```cpp
#include <iostream>

using namespace std;

int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(nullptr);

    // FAST: Just inserts newline
    cout << "Line 1\n";
    cout << "Line 2\n";

    // SLOW: Inserts newline AND flushes output stream
    cout << "Line 3" << endl; 

    return 0;
}
```

## 4. Building Output in a String (fputs/fwrite for Speed)

For maximum output speed, especially with many small strings, building a large output buffer and writing it all at once using C-style `fputs` or `fwrite` avoids frequent stream interactions.

**Compilable Snippet:**
```cpp
#include <iostream>
#include <string>
#include <cstdio>

using namespace std;

int main() {
    string out_buffer;
    out_buffer.reserve(100000); // Reserve memory to prevent reallocation

    for (int i = 1; i <= 5; ++i) {
        out_buffer += to_string(i) + " ";
    }
    out_buffer += "\n";

    // Fast C-style output
    fputs(out_buffer.c_str(), stdout);
    
    // Alternatively, using fwrite:
    // fwrite(out_buffer.c_str(), 1, out_buffer.size(), stdout);

    return 0;
}
```

## 5. Reading 10^6 Integers Fast (Custom Fast I/O)

For extreme performance, avoiding standard parsers completely and using `getchar_unlocked()` (or `_getchar_nolock()` on Windows) to build integers manually is the absolute fastest way to read.

**Compilable Snippet:**
```cpp
#include <cstdio>

// Super fast integer reader
inline void readInt(int &n) {
    n = 0;
    int ch = getchar(); // Use getchar_unlocked() on POSIX systems for even more speed
    int sign = 1;
    
    while (ch < '0' || ch > '9') {
        if (ch == '-') sign = -1;
        ch = getchar();
    }
    while (ch >= '0' && ch <= '9') {
        n = (n << 3) + (n << 1) + (ch - '0'); // n = n * 10 + digit
        ch = getchar();
    }
    n *= sign;
}

int main() {
    int num;
    // Simulate reading one number, e.g. for reading 10^6 numbers call this in a loop
    // readInt(num); 
    // printf("%d\n", num);
    
    return 0;
}
```

## 6. The `getline` After `cin` Trap

**The Trap:**
When you read using `cin >> value`, it leaves the trailing newline character `\n` in the input buffer. If you immediately follow this with `getline(cin, str)`, `getline` will see the `\n` immediately, read an empty string, and stop.

**The Fix:**
Use `cin.ignore()` to consume the leftover newline before calling `getline`.

**Compilable Snippet:**
```cpp
#include <iostream>
#include <string>

using namespace std;

int main() {
    int id;
    string name;

    // Assume input:
    // 42
    // John Doe

    cout << "Enter ID: ";
    cin >> id;

    // TRAP: cin leaves '\n' in the buffer. 
    // If we do getline(cin, name) now, name will be empty.

    // FIX: Ignore the remaining newline (and any other spaces until newline)
    // Limits the count to 256 or until '\n' is encountered.
    cin.ignore(256, '\n'); 

    cout << "Enter Name: ";
    getline(cin, name);

    cout << "ID: " << id << ", Name: " << name << "\n";

    return 0;
}
```
