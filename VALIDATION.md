**Validation and observed results — revision 2, 10 October 2026**

The user ran revision 1 on a native GitHub Mac runner and supplied the log and screenshot. That run used macOS 26.6.2, Xcode 26.6 (17F113), Apple Clang 21.0.0 (clang-2100.1.1.101), Apple linker ld-1267, ARM64, LTO off.

| Original native case | Observed result |
|---|---|
| `near-custom` | PASS |
| `far-text` | PASS |
| `far-custom` | LINK_FAILED: call from `_cold_handler+0x8` to `_hot_callback`, displacement -167772180 bytes (160 MiB + 20 bytes backwards), beyond the direct B/BL range. |

The linker also warned that `__TEXT,__easrt` had unwind information but lacked the `regular,pure_instructions` code-section flag. Revision 1's declaration was incomplete. Its successful compile-to-assembly check did not validate section flags; treating that as sufficient was a test-design error.

Revision 2 corrects the declaration and adds pre-link object and post-link executable flag checks. A fourth case intentionally preserves the old declaration for comparison. A native Apple linker run of this corrected revision is still pending. Correcting the warning alone does not establish that the long-range call will link successfully.

**Revision 2 checks performed**

| Check | Result |
|---|---|
| Exact revised header and probe, Compiler Explorer upstream Clang 22.1, `--target=arm64-apple-macos14`, C++20 `-O2 -Wall -Wextra -Werror` | All three source variants compiled to assembly successfully: ordinary text, corrected custom section, and deliberately unflagged custom section. |
| Emitted assembly directives | Corrected custom code emits `.section __TEXT,__easrt,regular,pure_instructions`; the diagnostic comparison emits `.section __TEXT,__easrt`. The ordinary-text control emits no `__easrt`. |
| Section-flag parser | Accepted correctly flagged metadata and explicitly permitted the unflagged diagnostic fixture. Rejected missing instruction flags in a corrected case, an incorrect section type, and an incorrect section name. |
| Workflow failure handling, injected diagnostics | A range error in corrected `far-custom` gives `LINK_FAILED` and process exit 1. The same error in the deliberately unflagged comparison gives `UNFLAGGED_RANGE_ERROR`, retains `link_status: LINK_FAILED`, and exits 0 as a diagnostic result. |
| Other injected failures | An unrelated linker error and a compiler failure in the unflagged comparison still exit 1. Missing instruction flags in the corrected case give `INVALID_TEST` and exit 1 before linking. |
| Source generation and workflow | All four cases generate; each far case has 160 padding atoms. The parsed workflow matrix matches the script's four cases. |

The injected-diagnostic checks exercise Python control flow using mocks; they are not compiler/linker runs. The revised cross-compilation checks use upstream Clang, not Apple Clang or Apple `ld`. Native linking, emitted Mach-O object/executable flags, and execution of revision 2 must still be checked by the supplied Mac workflow.

**Earlier checks, retained for context**

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
| Original `src/section_probe.cpp`, upstream Clang 22.1 targeting macOS ARM64 | Ordinary-text and custom-section versions both compiled successfully. This did not catch the missing flags; see the correction above. |
| Python generator | The three original cases generated successfully on a non-Mac host. Far cases contain 160 individually labelled 1 MiB padding atoms and an explicit order file. |
| Layout verifier | A representative valid map/symbol fixture passed. Near-distance, incorrect-cold-section, and incorrect-caller-section fixtures were rejected as `INVALID_TEST`. |
| Workflow | YAML parsed; manual inputs, matrix, commands and source paths checked. |
| ZIP | File integrity and inclusion of the workflow/source files checked; generated build outputs excluded. |

Compile-to-assembly tests used the exact header content with the include expanded; they do not establish native Windows or Apple linker behavior. MSVC x86-64's assembly listing spells the code area as `easrt`; its formatting differs from the ARM64 listing's `.easrt` spelling.

The published source and exact local assertion example were tested separately from the synthetic Mac reachability probe. No frame-time, cache, or throughput benchmark was performed. The project makes no performance percentage claim.

Previous independent Linux ARM64 range test: [Compiler Explorer, 256 MiB between ordinary and custom code](https://godbolt.org/z/vTWKnvdh3). That test linked and executed with Clang 22.1/LLD 22.1 and GCC 15.2/GNU ld 2.44. It supports removing a blanket ARM exclusion; it is not a native Mac result.
