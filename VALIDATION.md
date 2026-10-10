**Validation performed before packaging — 10 October 2026**

The native Apple linker test has not been run. The workflow in this project is the means to obtain that result on GitHub's Mac runner.

| Check | Result |
|---|---|
| Real assertion example, GCC 13.3, Linux x86-64, C++20 `-O2 -Wall -Wextra -Werror` | Compiled, linked and ran with custom sections enabled and disabled. |
| Normal path of that example | Exit zero in both configurations. |
| Deliberate failure path of that example | Printed the expected assertion diagnostic and aborted in both configurations. |
| Linux linked section inspection | `.easrt` present when custom placement is enabled, absent when disabled. |
| Annotation header with a fatal helper and `[[unlikely]]` caller, GCC 15.2, Linux ARM64 | Compiler Explorer compile-to-assembly passed with warnings treated as errors. |
| Same header/probe, Clang 22.1, Linux ARM64 | Passed; dedicated `.easrt` emitted. |
| Same header/probe, MSVC 19.51 (VS18.6), Windows x86-64 and ARM64 | Both passed; distinct failure-handler code areas shown in compiler listings. |
| Same header/probe, clang-cl 22.1.6, Windows x86-64 and ARM64 | Both passed; dedicated `.easrt` emitted. |
| Same header/probe, upstream Clang 22.1 targeting macOS ARM64 | Both default and explicitly enabled custom-section configurations passed. Default uses ordinary text; opt-in emits `__TEXT,__easrt`. |
| Actual `src/section_probe.cpp`, upstream Clang 22.1 targeting macOS ARM64 | Ordinary-text and custom-section versions both compiled successfully with warnings treated as errors. |
| Python generator | All three cases generated successfully on a non-Mac host. Far cases contain 160 individually labelled 1 MiB padding atoms and an explicit order file. |
| Layout verifier | A representative valid map/symbol fixture passed. Near-distance, incorrect-cold-section, and incorrect-caller-section fixtures were rejected as `INVALID_TEST`. |
| Workflow | YAML parsed; manual inputs, matrix, commands and source paths checked. |
| ZIP | File integrity and inclusion of the workflow/source files checked; generated build outputs excluded. |

Compile-to-assembly tests used the exact header content with the include expanded; they do not establish native Windows or Apple linker behavior. MSVC x86-64's assembly listing spells the code area as `easrt`; its formatting differs from the ARM64 listing's `.easrt` spelling.

The published source and exact local assertion example were tested separately from the synthetic Mac reachability probe. No frame-time, cache, or throughput benchmark was performed. The project makes no performance percentage claim.

Previous independent Linux ARM64 range test: [Compiler Explorer, 256 MiB between ordinary and custom code](https://godbolt.org/z/vTWKnvdh3). That test linked and executed with Clang 22.1/LLD 22.1 and GCC 15.2/GNU ld 2.44. It supports removing a blanket ARM exclusion; it is not a native Mac result.
