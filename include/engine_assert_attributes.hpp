#pragma once

// C++20; include this from every declaration/definition of a failure helper.
// ENGINE_ENABLE_ASSERT_SECTION must have the same value throughout a build.
// These policies deliberately do not depend on x86-64 versus ARM64.

#if defined(_MSC_VER)
#  define ENGINE_NOINLINE __declspec(noinline)
#elif defined(__clang__) || defined(__GNUC__)
#  define ENGINE_NOINLINE __attribute__((noinline))
#else
#  define ENGINE_NOINLINE
#endif

#if defined(__clang__) || defined(__GNUC__)
#  define ENGINE_COLD __attribute__((cold))
#else
// MSVC has no equivalent function-level cold attribute here.
#  define ENGINE_COLD
#endif

#ifndef ENGINE_ENABLE_ASSERT_SECTION
#  if defined(__APPLE__)
// Enable explicitly after the native Mac long-range test passes for your tools.
#    define ENGINE_ENABLE_ASSERT_SECTION 0
#  elif defined(__ELF__) || (defined(_WIN32) && defined(_MSC_VER))
#    define ENGINE_ENABLE_ASSERT_SECTION 1
#  else
#    define ENGINE_ENABLE_ASSERT_SECTION 0
#  endif
#endif

#if ENGINE_ENABLE_ASSERT_SECTION != 0 && ENGINE_ENABLE_ASSERT_SECTION != 1
#  error ENGINE_ENABLE_ASSERT_SECTION must be 0 or 1
#endif

#if !ENGINE_ENABLE_ASSERT_SECTION
#  define ENGINE_ASSERT_SECTION
#elif defined(__APPLE__) && (defined(__clang__) || defined(__GNUC__))
#  define ENGINE_ASSERT_SECTION __attribute__((section("__TEXT,__easrt")))
#elif defined(_WIN32) && defined(_MSC_VER)
// Covers MSVC and clang-cl. Keep the PE section name within eight characters.
#  define ENGINE_ASSERT_SECTION __declspec(code_seg(".easrt"))
#elif defined(__ELF__) && (defined(__clang__) || defined(__GNUC__))
// A dedicated output section under the ordinary GNU ld / ELF LLD policies.
// Custom linker scripts must also retain and place this executable section.
#  define ENGINE_ASSERT_SECTION __attribute__((section(".easrt")))
#else
#  error No custom assertion-section policy defined for this toolchain
#endif

#define ENGINE_FAILURE_ATTRIBUTES ENGINE_COLD ENGINE_NOINLINE ENGINE_ASSERT_SECTION

// Use standard [[unlikely]] at the failure branch and [[noreturn]] only on
// handlers that really cannot return. Neither is an architecture-specific
// intrinsic. Returning ensure/report handlers must not have [[noreturn]].
