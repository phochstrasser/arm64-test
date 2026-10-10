**Recommended assertion/failure annotations**

Scope: modern C++20, GCC/Clang on ELF Linux, MSVC/clang-cl on Windows, and Apple Clang on macOS. These are failure-handler policies, not annotations to apply to all engine functions. The same defaults apply to x86-64 and ARM64. Unsupported platforms default to no custom section.

| Platform/compiler | On a rare failure handler | Custom placement policy in this header |
|---|---|---|
| Linux, GCC | `__attribute__((cold, noinline))` | Enabled: `__attribute__((section(".easrt")))` |
| Linux, Clang | `__attribute__((cold, noinline))` | Enabled: `__attribute__((section(".easrt")))` |
| Windows, MSVC | `__declspec(noinline)`; no corresponding `cold` function annotation here | Enabled: `__declspec(code_seg(".easrt"))` |
| Windows, clang-cl | `__attribute__((cold))` and `__declspec(noinline)` | Enabled: `__declspec(code_seg(".easrt"))` |
| macOS, Apple Clang | `__attribute__((cold, noinline))` | Disabled initially. Opt-in after the native test: `__attribute__((section("__TEXT,__easrt")))` |

This chooses a short dedicated section name, not `.text.unlikely.*`, so the usual ELF linker policy does not simply merge it into ordinary `.text`. No `-z keep-text-section-prefix` option is required for this chosen custom-section scheme. If you instead rely on compiler-created `.text.unlikely.*`, ELF LLD's `-z keep-text-section-prefix` is one alternative layout policy. Do not assume the two schemes are interchangeable under a custom linker script.

The Windows and ELF enablement is a recommended starting policy, not a claim that every large image and linker configuration has been tested. Confirm your final link map and use production-size link tests. The Mac default is a toolchain/format exception; there is no blanket `!ARM` condition.

For all rows:

- Put `[[unlikely]]` on the failure branch in C++20. It is a hint, not an execution guarantee; profile-guided optimization may take precedence.
- Put `[[noreturn]]` on a handler that always terminates and cannot return to its caller. Omit it for returning `ensure`/report functions. A debugger break from which you can continue does not establish `noreturn`.
- `noexcept` is an optional API promise about exception behavior, not a cold-placement optimization. The fatal example uses it because its failure handler prints and aborts.
- Keep the comparison and normal path in the caller. Apply cold/noinline/section attributes to failure implementation only.

```cpp
#include "engine_assert_attributes.hpp"

[[noreturn]] ENGINE_FAILURE_ATTRIBUTES
void FailAssertion(const char* expression, const char* file, int line) noexcept;

// In ordinary engine code:
// if (!condition) [[unlikely]] {
//     FailAssertion("condition", __FILE__, __LINE__);
// }
```

Use the same attributes on the definition; the packaged working example shows it. The header keeps `ENGINE_COLD`, `ENGINE_NOINLINE`, and `ENGINE_ASSERT_SECTION` independent, and combines them as `ENGINE_FAILURE_ATTRIBUTES` for convenience.

**Intrinsics: none are required for this policy**

| Operation | Recommendation |
|---|---|
| Mark the failure branch unlikely | C++20 `[[unlikely]]`. For an existing pre-C++20 Clang/GCC expression-style macro, `__builtin_expect(!!condition, 0)` is a possible fallback; this project does not need it. |
| Terminate a fatal assertion | The example uses standard `std::abort()` after reporting. No per-architecture assembly is needed. |
| Break into a debugger | Optional, separate from placement: MSVC/clang-cl provide `__debugbreak()`; Clang provides `__builtin_debugtrap()`. A break can resume; use your debugger-detection and continuation policy. The example does not add this behavior. |
| Tell the optimizer something is impossible | Do not substitute `__assume`, `__builtin_assume`, `__builtin_unreachable`, or `std::unreachable()` for a runtime failure check. These are stronger correctness promises, not likelihood hints. A declared `[[noreturn]]` handler already conveys its control-flow contract. |

Do not add `always_inline`/`__forceinline`, `hot`, `optnone`, `noipa`, or hand-written long-branch assembly to these handlers by default. `noinline` is sufficient for the intended outlining policy. Configure whether assertions exist in a build separately; a disabled assertion need not become an optimizer assumption.

**Why this is the current recommendation**

`cold` supplies optimization information; `noinline` preserves an out-of-line helper; custom placement controls emitted code location. They solve different parts of the problem. A cold annotation alone does not guarantee physical grouping on every format/linker. This header makes that policy explicit while allowing the Mac custom section to be enabled after a native test.

Published research justifies the locality optimization as an engineering starting point. A later engine benchmark is needed to quantify the incremental gain; it is not required before creating this small failure-handling abstraction. Inspect the linked image even when compilation accepts all attributes.

Primary references checked 10 October 2026:

- [GCC common attributes](https://gcc.gnu.org/onlinedocs/gcc/Common-Attributes.html): `cold`, `noinline`, and named sections.
- [Clang attributes](https://clang.llvm.org/docs/AttributeReference.html): cold frequency hints, noinline, `code_seg`, and `[[unlikely]]`.
- [Microsoft code_seg](https://learn.microsoft.com/en-us/cpp/cpp/code-seg-declspec?view=msvc-170): function and template code placement.
- [Microsoft noinline](https://learn.microsoft.com/en-us/cpp/cpp/noinline?view=msvc-170).
- [Microsoft __assume](https://learn.microsoft.com/en-us/cpp/intrinsics/assume?view=msvc-170): optimizer assumptions are not runtime checks.
- [Microsoft __debugbreak](https://learn.microsoft.com/en-us/cpp/intrinsics/debugbreak?view=msvc-170).
- [Clang language extensions](https://clang.llvm.org/docs/LanguageExtensions.html): `__builtin_debugtrap`.
- [LLD ELF layout policy](https://lld.llvm.org/ELF/linker_script.html).
- [GitHub runner specifications](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).
