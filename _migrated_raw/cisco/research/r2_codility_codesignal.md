# Research: Codility and CodeSignal Function-Signature Harnesses

Both Codility and CodeSignal automate coding assessments by wrapping algorithm logic in I/O scaffolding. Instead of writing `main()` functions and parsing standard input/output (`std::cin` / `std::cout`), developers are provided with function stubs. The platform's hidden harness handles parsing the test cases, invoking the stub, and asserting the returned values against expected output.

## 1. Codility

**Harness & Scaffolding**
Codility hides all I/O parsing. The platform injects your code into an internal test runner that instantiates the class and calls the method. You only implement the core logic. Standard output (e.g., `std::cout`) can be used for debugging, but the actual evaluation is based strictly on the function's return value.

**Typical Parameter Types & Checking**
- **Inputs**: Commonly uses references to standard containers to avoid deep copies (e.g., `std::vector<int>&`, `std::string&`).
- **Return Values**: Typically primitive types (`int`, `bool`) or standard containers. The test runner directly compares the returned object to the expected result.

**ACTUAL C++ Stub Example**
```cpp
#include <vector>
// Codility typically requires your function inside a Solution class
class Solution {
public:
    int solution(std::vector<int> &A) {
        // Core logic here
        // No I/O parsing required
        return 0;
    }
};
```
*Source: [StackOverflow / Codility Discussions](https://stackoverflow.com/questions/3553296/c-c-codility-test)*

## 2. CodeSignal

**Harness & Scaffolding**
CodeSignal uses global functions rather than class methods. The environment reads JSON-like test case definitions behind the scenes, deserializes them into native C++ types, and passes them as arguments to your function. CodeSignal provides visible test cases (where inputs and expected outputs are fully shown) and hidden tests (where execution time or edge case failures are shown without revealing the exact input). Users can also create custom test cases via a UI panel.

**Typical Parameter Types & Checking**
- **Inputs**: Frequently uses pass-by-value or pass-by-reference for complex structures. Arrays are passed as `std::vector<int>`, matrices as `std::vector<std::vector<int>>`, and strings as `std::string`.
- **Return Values**: The return value is serialized back and compared against the expected output. For array outputs, the elements and their order must perfectly match the expected `std::vector`.

**ACTUAL C++ Stub Example**
```cpp
#include <vector>
#include <string>

// CodeSignal uses global functions
std::vector<int> solution(std::vector<std::vector<int>> matrix, std::string direction) {
    // Core logic here
    // No I/O parsing required
    std::vector<int> result;
    return result;
}
```
*Source: [CodeSignal Developer Documentation](https://codesignal.com/developers/)*

## Conclusion
Both platforms abstract away the boilerplate of parsing strings into arrays or numbers. 
- **Codility** encapsulates the solution within a `class Solution`.
- **CodeSignal** uses top-level global functions.
Both heavily rely on C++ STL containers like `std::vector` and `std::string` to represent arrays and strings respectively, evaluating correctness exclusively via the function's return value.
