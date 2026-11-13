#!/usr/bin/env python3
"""Bundle a macOS QEMU install tree into a relocatable directory.

The Homebrew qemu-virgl recipe links several keg-only dylibs by absolute path.
dylibbundler handles some of them but misses direct links and produces duplicate
LC_RPATH entries when the source binary already had the target rpath.  This
script copies every non-system dependency recursively, rewrites the install
names to @loader_path (dylibs) or @executable_path/../lib (binaries), removes
all LC_RPATH entries, adds exactly one executable rpath, and signs the result.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def otool_deps(path: Path) -> list[str]:
    out = subprocess.check_output(["otool", "-L", str(path)], text=True)
    deps = []
    for line in out.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        dep = line.split(" (", 1)[0].strip()
        if dep:
            deps.append(dep)
    return deps


def otool_rpaths(path: Path) -> list[str]:
    out = subprocess.check_output(["otool", "-l", str(path)], text=True)
    result = []
    lines = out.splitlines()
    for index, line in enumerate(lines):
        if "cmd LC_RPATH" in line:
            for follow in lines[index + 1 : index + 5]:
                match = follow.strip()
                if match.startswith("path "):
                    result.append(match[5:].split(" (offset", 1)[0])
                    break
    return result


def is_homebrew(path: str) -> bool:
    return path.startswith("/opt/homebrew/") or path.startswith("/usr/local/")


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <dist-dir>", file=sys.stderr)
        return 2
    dist = Path(sys.argv[1]).resolve()
    bindir = dist / "bin"
    libdir = dist / "lib"
    libdir.mkdir(parents=True, exist_ok=True)
    binaries = [path for path in bindir.iterdir() if path.is_file()]
    queue: list[Path] = list(binaries)
    copied: set[Path] = set()

    while queue:
        current = queue.pop(0)
        for dep in otool_deps(current):
            if dep.startswith(("@loader_path/", "@executable_path/")):
                continue
            if not is_homebrew(dep):
                continue
            source = Path(dep)
            target = libdir / source.name
            if target not in copied:
                if not source.exists():
                    raise SystemExit(f"missing dependency {source} referenced by {current}")
                if target.exists():
                    target.unlink()
                shutil.copy2(source, target)
                copied.add(target)
                queue.append(target)
            relative = (
                f"@loader_path/{target.name}"
                if current.parent == libdir
                else f"@executable_path/../lib/{target.name}"
            )
            subprocess.run(
                ["install_name_tool", "-change", dep, relative, str(current)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    for path in [*binaries, *sorted(libdir.iterdir())]:
        if not path.is_file():
            continue
        for rpath in otool_rpaths(path):
            subprocess.run(
                ["install_name_tool", "-delete_rpath", rpath, str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        if path.parent == bindir:
            subprocess.run(
                ["install_name_tool", "-add_rpath", "@executable_path/../lib", str(path)],
                check=True,
            )

    entitlements = dist / "entitlements.plist"
    for path in sorted(libdir.iterdir()):
        if path.is_file() and path.suffix == ".dylib":
            subprocess.run(["codesign", "--force", "--sign", "-", str(path)], check=True)
    for path in binaries:
        cmd = ["codesign", "--force", "--sign", "-"]
        if path.name == "qemu-system-aarch64" and entitlements.exists():
            cmd += ["--entitlements", str(entitlements)]
        cmd.append(str(path))
        subprocess.run(cmd, check=True)

    print(f"bundled {len(copied)} dylibs into {libdir}")
    for path in binaries:
        print(subprocess.check_output(["otool", "-L", str(path)], text=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
