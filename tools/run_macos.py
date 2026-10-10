#!/usr/bin/env python3
"""Generate a large macOS ARM64 image and test calls across code sections.

Requires Python 3.9+ and a selected Xcode installation for a native test.
--generate-only works on any host and does not claim a successful link test.
"""

import argparse
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
CASES = ("near-custom", "far-text", "far-custom", "far-custom-unflagged")
MIB = 1024 * 1024


class ProbeFailure(RuntimeError):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def run(args, cwd, log_name, failure_status="BUILD_FAILED"):
    command = shlex.join(str(arg) for arg in args)
    print("+ " + command, flush=True)
    result = subprocess.run(
        [str(arg) for arg in args], cwd=cwd, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300,
    )
    (cwd / log_name).write_text(
        "$ " + command + "\n" + result.stdout +
        "\nexit code: " + str(result.returncode) + "\n", encoding="utf-8",
    )
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n", flush=True)
    if result.returncode:
        raise ProbeFailure(failure_status, f"Command exited {result.returncode}: {command}")
    return result.stdout


def generate(work, far):
    work.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PROJECT / "src/section_probe.cpp", work / "probe.cpp")
    assembly = [".section __TEXT,__text,regular,pure_instructions"]
    order = ["_main", "_hot_entry", "_hot_callback"]
    # Each 1 MiB atom leaves insertion points for linker branch islands.
    # A single 160 MiB atom could fail for an unrelated lack of insertion points.
    for index in range(160 if far else 0):
        name = f"_section_test_padding_{index:04d}"
        assembly += [
            ".p2align 2", f".globl {name}", f".no_dead_strip {name}",
            name + ":", "ret", f".space {MIB - 4}, 0",
        ]
        order.append(name)
    assembly.append(".subsections_via_symbols")
    order.append("_cold_handler")
    (work / "padding.s").write_text("\n".join(assembly) + "\n", encoding="utf-8")
    (work / "order.txt").write_text("\n".join(order) + "\n", encoding="utf-8")


def verify_layout(symbol_text, map_text, custom, far):
    symbols = {}
    for line in symbol_text.splitlines():
        fields = line.split()
        if len(fields) >= 3 and re.fullmatch(r"[0-9a-fA-F]+", fields[0]):
            symbols[fields[-1]] = int(fields[0], 16)
    names = ("_main", "_hot_entry", "_hot_callback", "_cold_handler")
    for name in names:
        if name not in symbols:
            raise ProbeFailure("INVALID_TEST", "Missing symbol: " + name)
        print(f"{name}: 0x{symbols[name]:x}", flush=True)
    gaps = {}
    for hot in ("_hot_entry", "_hot_callback"):
        gap = abs(symbols[hot] - symbols["_cold_handler"])
        gaps[hot] = gap
        print(f"{hot} <-> _cold_handler: {gap / MIB:.3f} MiB", flush=True)
        # Margin also accounts for instruction offsets within these tiny bodies.
        if far and gap <= 128 * MIB + 4096:
            raise ProbeFailure("INVALID_TEST", "Layout did not force a far call")
        if not far and gap >= 128 * MIB:
            raise ProbeFailure("INVALID_TEST", "Near control case is not near")
    expected = "__easrt" if custom else "__text"
    found_section = False
    hot_in_text = set()
    for line in map_text.splitlines():
        fields = line.split()
        if len(fields) == 4 and fields[2] == "__TEXT" and fields[3] in (expected, "__text"):
            start, size = int(fields[0], 16), int(fields[1], 16)
            if fields[3] == "__text":
                hot_in_text.update(name for name in names[:-1] if start <= symbols[name] < start + size)
            if fields[3] == expected and start <= symbols["_cold_handler"] < start + size:
                found_section = True
                print("Verified section: " + line, flush=True)
    if not found_section:
        raise ProbeFailure("INVALID_TEST", "Cannot verify cold_handler's section in the link map")
    if hot_in_text != set(names[:-1]):
        raise ProbeFailure("INVALID_TEST", "Cannot verify ordinary callers in __TEXT,__text")
    return {
        "addresses": {name: hex(symbols[name]) for name in names},
        "gaps_bytes": gaps, "cold_section": "__TEXT," + expected,
    }


def verify_section_flags(load_commands, section_name, require_instructions):
    """Read numeric section flags from Apple's non-verbose `otool -l` output."""
    sections = []
    section = None
    for line in load_commands.splitlines():
        fields = line.split()
        if fields == ["Section"] or line.strip().startswith("Load command "):
            if section is not None:
                sections.append(section)
            section = {} if fields == ["Section"] else None
        elif section is not None and len(fields) >= 2:
            if fields[0] in ("sectname", "segname", "flags"):
                section[fields[0]] = fields[1]
    if section is not None:
        sections.append(section)
    for section in sections:
        if section.get("segname") == "__TEXT" and section.get("sectname") == section_name:
            if "flags" not in section:
                raise ProbeFailure("INVALID_TEST", "No section flags in otool output")
            flags = int(section["flags"], 0)
            regular = (flags & 0xff) == 0
            pure_instructions = bool(flags & 0x80000000)
            print(f"__TEXT,{section_name} flags: 0x{flags:08x}; "
                  f"regular={regular}, pure_instructions={pure_instructions}", flush=True)
            if not regular or (require_instructions and not pure_instructions):
                raise ProbeFailure("INVALID_TEST", "Missing regular,pure_instructions code-section flags")
            return {"section": "__TEXT," + section_name, "flags": hex(flags),
                    "regular": regular, "pure_instructions": pure_instructions}
    raise ProbeFailure("INVALID_TEST", "Section missing in otool output: " + section_name)


def test_case(case, out, lto, generate_only):
    work = out / case
    custom, far = case != "far-text", case != "near-custom"
    unflagged = case == "far-custom-unflagged"
    generate(work, far)
    result = {"case": case, "lto": lto, "status": "STARTED",
              "explicit_instruction_flags": not unflagged, "test_revision": 2}
    try:
        if generate_only:
            result["status"] = "GENERATED_ONLY"
            return result
        if platform.system() != "Darwin" or platform.machine() != "arm64":
            raise ProbeFailure("ENVIRONMENT_ERROR", "Native test requires macOS ARM64; use GitHub Actions")
        if not shutil.which("xcrun"):
            raise ProbeFailure("ENVIRONMENT_ERROR", "Xcode Command Line Tools / xcrun missing")

        run(["uname", "-a"], work, "host.log")
        run(["sw_vers"], work, "macos.log")
        run(["xcodebuild", "-version"], work, "xcode.log")
        run(["xcrun", "clang++", "--version"], work, "compiler.log")

        lto_flags = [] if lto == "off" else ["-flto=" + lto]
        compile_flags = [
            "-arch", "arm64", "-std=c++20", "-O2", "-Wall", "-Wextra",
            "-Werror", "-fno-optimize-sibling-calls", "-I", str(PROJECT / "include"),
            f"-DPROBE_CUSTOM_SECTION={int(custom)}",
            f"-DPROBE_UNFLAGGED_CUSTOM={int(unflagged)}",
        ]
        run(["xcrun", "clang++", *compile_flags, *lto_flags,
             "-c", "probe.cpp", "-o", "probe.o"], work, "compile.log")
        expected_section = "__easrt" if custom else "__text"
        if lto == "off":
            # Validate the actual object metadata, not merely the source spelling.
            object_commands = run(["xcrun", "otool", "-l", "probe.o"],
                                  work, "object-sections.log", "INVALID_TEST")
            result["object_section"] = verify_section_flags(
                object_commands, expected_section, require_instructions=not unflagged)
        else:
            # The LTO input is bitcode; inspect the native section after linking.
            result["object_section"] = "LTO bitcode; check deferred until final link"
        run(["xcrun", "clang", "-arch", "arm64", "-c", "padding.s", "-o", "padding.o"],
            work, "assemble.log")
        # Use the actual Apple linker selected by Xcode, not ELF LLD or ld64.lld.
        run(["xcrun", "clang++", "-arch", "arm64", *lto_flags, "-v", "-Wl,-v",
             "-Wl,-order_file,order.txt", "-Wl,-map,probe.map",
             "probe.o", "padding.o", "-o", "probe"], work, "link.log", "LINK_FAILED")
        symbols = run(["xcrun", "nm", "-n", "probe"], work, "symbols.log", "INVALID_TEST")
        load_commands = run(["xcrun", "otool", "-l", "probe"],
                            work, "load-commands.log", "INVALID_TEST")
        result["linked_section"] = verify_section_flags(
            load_commands, expected_section, require_instructions=not unflagged)
        result.update(verify_layout(symbols, (work / "probe.map").read_text(), custom, far))
        run(["./probe"], work, "execute.log", "RUN_FAILED")
        result["status"] = "PASS"
        print(f"PASS {case}: linked, verified placement and reach, executed with exit code 0", flush=True)
    except ProbeFailure as exc:
        result.update(status=exc.status, error=str(exc))
        if unflagged and exc.status == "LINK_FAILED":
            link_log = (work / "link.log").read_text()
            if "arm64_b26" in link_log and "B/BL out of range" in link_log:
                # This case deliberately reproduces the bad original declaration.
                # Record its range error without marking it as a successful link.
                result.update(status="UNFLAGGED_RANGE_ERROR", link_status="LINK_FAILED")
                print("Diagnostic control reproduced the unflagged range error; "
                      "the corrected far-custom case remains the deciding test.", flush=True)
        print(f"{exc.status} {case}: {exc}", file=sys.stderr, flush=True)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        result.update(status="HARNESS_ERROR", error=str(exc))
        print(f"HARNESS_ERROR {case}: {exc}", file=sys.stderr, flush=True)
    finally:
        (work / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("all", *CASES), default="all")
    parser.add_argument("--lto", choices=("off", "thin", "full"), default="off")
    parser.add_argument("--out", type=Path, default=PROJECT / "build")
    parser.add_argument("--generate-only", action="store_true")
    args = parser.parse_args()
    cases = CASES if args.case == "all" else (args.case,)
    results = [test_case(case, args.out.resolve(), args.lto, args.generate_only) for case in cases]
    summary = "| Case | LTO | Result |\n|---|---|---|\n" + "".join(
        f"| {r['case']} | {r['lto']} | {r['status']} |\n" for r in results
    )
    print(summary, flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
            stream.write(summary)
    def acceptable(result):
        if args.generate_only:
            return result["status"] == "GENERATED_ONLY"
        return result["status"] == "PASS" or (
            result["case"] == "far-custom-unflagged" and
            result["status"] == "UNFLAGGED_RANGE_ERROR")
    return 0 if all(acceptable(r) for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
