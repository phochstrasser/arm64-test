#include "engine_assert_attributes.hpp"

#include <cstdio>
#include <cstdlib>

// Only failure handling receives these attributes, not the ordinary caller.
[[noreturn]] ENGINE_FAILURE_ATTRIBUTES
void fail_assertion(const char* expression, const char* file, int line) noexcept {
    std::fprintf(stderr, "Assertion failed: %s (%s:%d)\n", expression, file, line);
    std::abort();
}

// This reference macro is always enabled and evaluates its condition once.
// Configure assertion removal separately in your engine's build policy.
#define ENGINE_CHECK(expression)                                      \
    do {                                                              \
        if (!(expression)) [[unlikely]] {                             \
            fail_assertion(#expression, __FILE__, __LINE__);            \
        }                                                             \
    } while (false)

int main(int argc, char**) {
    // Normal invocation passes. Any extra argument deliberately fails.
    ENGINE_CHECK(argc == 1);
    return 0;
}
