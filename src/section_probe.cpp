// Synthetic macOS ARM64 branch-reach test. This is not a performance benchmark.
#if !defined(__APPLE__) || !defined(__aarch64__)
#  error This probe targets macOS ARM64
#endif

#ifndef PROBE_CUSTOM_SECTION
#  error Define PROBE_CUSTOM_SECTION as 0 or 1
#endif

#define ENGINE_ENABLE_ASSERT_SECTION PROBE_CUSTOM_SECTION
#include "engine_assert_attributes.hpp"

#define PROBE_HOT ENGINE_NOINLINE __attribute__((section("__TEXT,__text")))
#if PROBE_CUSTOM_SECTION
#  define PROBE_COLD ENGINE_FAILURE_ATTRIBUTES
#else
// Explicit ordinary-text control case for the identical call graph.
#  define PROBE_COLD ENGINE_COLD ENGINE_NOINLINE __attribute__((section("__TEXT,__text")))
#endif

extern "C" {
PROBE_HOT int hot_callback(int x) {
    asm volatile("" : "+r"(x));
    return x + 1;
}

// It deliberately returns: this exercises a call back from cold to hot code.
// A fatal-only noreturn probe could miss that direction of branch-range failure.
PROBE_COLD int cold_handler(int x) {
    return hot_callback(x) + 1;
}

PROBE_HOT int hot_entry(int x) {
    return cold_handler(x) + 1;
}
}

PROBE_HOT int main() {
    return hot_entry(39) == 42 ? 0 : 1;
}
