**ARM64 assertion-section test project**

This repository runs a standalone macOS ARM64 compiler/linker experiment on GitHub Actions. It does not need your engine, Unreal, a local ARM machine, an Apple developer account, or additional Python packages. It also contains a portable C++20 annotation header and a small assertion example you can adapt to your engine.

The original single-file YAML generated all its C++ inside the workflow. This version separates that code into ordinary source files. Commit the whole project, including `.github/workflows/`, rather than copying just this new YAML.

**Run it on GitHub**

1. Extract the ZIP. Open the inner `arm64-assert-sections` folder; this is the repository root.
2. Create an empty GitHub repository. Commit and push the contents of this folder, including `.github`.
3. Open the repository's **Actions** tab and select **macOS ARM64 assertion sections**.
4. Click **Run workflow**. Start with runner `macos-26` and LTO `off`.
5. Inspect the three jobs. Their summaries show `PASS`, a build/link/run failure, or `INVALID_TEST`. Download the diagnostic artifacts if a job fails.

For example, from the extracted project folder, after creating your empty GitHub repository:

```sh
git init
git add .
git commit -m "Add ARM64 assertion-section tests"
git branch -M main
git remote add origin https://github.com/YOUR_ACCOUNT/YOUR_REPOSITORY.git
git push -u origin main
```

The workflow is manual; a push does not start it. For the Run workflow button to appear, the workflow must be on the repository's default branch. You may need to enable Actions if your repository or organization disables them.

**What the code actually does**

The call chain is `main -> hot_entry -> cold_handler -> hot_callback`. Each helper adds one to its input, so `hot_entry(39)` must return `42`. A successful executable returns exit code zero. The cold handler returns deliberately: the test needs to exercise branches out of a custom section as well as branches into it.

| Case | Layout | Purpose |
|---|---|---|
| `near-custom` | Small ordinary text plus `__TEXT,__easrt` | Confirms basic custom-section placement and execution. |
| `far-text` | All probe functions in ordinary `__TEXT,__text`; generated padding between callers and callee | Control case for range extension in ordinary text. |
| `far-custom` | Callers in ordinary text, handler in `__TEXT,__easrt`, with generated padding | Tests range extension into and out of the custom section. |

The two far cases generate 160 MiB of unexecuted padding during the build. It consists of 160 independently labelled 1 MiB pieces so the linker has insertion points for branch islands. The ZIP contains only the small generator, not the generated padding or executables.

The script verifies actual symbol distances above the approximately 128 MiB direct-call range, verifies the handler's section from the link map, and executes the program. It records the Xcode/compiler/linker versions. A source attribute or a successful small link alone is not counted as a successful long-range test.

**Interpret the result**

- All three `PASS`: these call/layout cases work with the recorded Apple tools and options. You can enable the Mac custom-section option for that toolchain, then repeat with the LTO and other flags you actually ship.
- `near-custom` and `far-text` pass, while `far-custom` has an out-of-range linker error: this demonstrates the kind of custom-section limitation described in the Unreal comment. Leave custom placement disabled for that configuration.
- `INVALID_TEST`: the intended layout could not be established or checked. This is not proof that the linker cannot handle custom sections.
- `BUILD_FAILED`, `ENVIRONMENT_ERROR`, or `HARNESS_ERROR`: inspect the logs; compilation or the test setup failed before establishing the intended experiment.
- `RUN_FAILED`: the executable linked but did not run successfully; inspect `execute.log`.

This is a branch-reach and basic execution test. It does not measure performance or validate every possible binary layout, exception-unwinding path, sanitizer, or engine configuration.

**Files**

| File | Role |
|---|---|
| `.github/workflows/macos-arm64-sections.yml` | Runs the three cases on GitHub's ARM64 Mac runner and preserves diagnostic files. |
| `src/section_probe.cpp` | The small C++ call chain being tested. |
| `tools/run_macos.py` | Generates padding and ordering, compiles and links, verifies addresses/sections, and runs the executable. Python standard library only. |
| `include/engine_assert_attributes.hpp` | Concrete annotation policy for an engine's failure helpers. |
| `examples/assertion_example.cpp` | Working fatal-assert example; normal invocation succeeds, any extra argument deliberately aborts. |
| `ANNOTATIONS.md` | Per-toolchain defaults, usage, intrinsic guidance, and sources. |
| `VALIDATION.md` | Checks performed before packaging and the native tests still pending. |

Build outputs are written to `build/` and ignored by Git. Actions uploads logs, JSON results, link maps, and order files; it does not upload the large object files or executables.

**Run locally when you have a Mac**

With Python 3.9+ and an ARM64 Mac with Xcode selected:

```sh
python3 tools/run_macos.py
python3 tools/run_macos.py --case far-custom --lto thin
```

From any computer, you can inspect the generated source and order files without building:

```sh
python3 tools/run_macos.py --generate-only
```

That mode records `GENERATED_ONLY`, never `PASS`. You can delete `build/` when finished. Rerun with `--lto thin` or `--lto full` after the default case if that matches your intended engine build. The baseline intentionally does not add dead stripping or your engine's custom linker flags.

**Build the separate annotation example**

On Linux with GCC or Clang:

```sh
g++ -std=c++20 -O2 -Iinclude examples/assertion_example.cpp -o assertion_example
./assertion_example
```

On macOS, use `clang++` instead of `g++`. On Windows, from a Visual Studio developer command prompt:

```bat
cl /std:c++20 /O2 /EHsc /Iinclude examples\assertion_example.cpp /Fe:assertion_example.exe
assertion_example.exe
```

To enable the optional Mac custom section, add `-DENGINE_ENABLE_ASSERT_SECTION=1`. To disable custom placement on any supported compiler, define the same macro as `0` (`/DENGINE_ENABLE_ASSERT_SECTION=0` with MSVC). Keep this setting consistent across declarations, definitions, and translation units.

This project contains source files, not an initialized `.git` directory, a remote repository, or pre-run GitHub results. No native Apple linker run has been performed before delivery.
