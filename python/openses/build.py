"""Compile the OpenSES Fortran sources with gfortran.

The compiler flags are the release flags from source/makefile, so an
executable built here computes exactly what a `make release` build
computes.  The source file list is read from the makefile as well, so the
makefile stays the single place where sources are registered.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Same flags as RELFFLAGS1 / RELFFLAGS2 / link line in source/makefile.
F95_FLAGS = ["-falign-commons", "-Wno-align-commons", "-pedantic"]
FOR_FLAGS = ["-falign-commons", "-Wno-align-commons", "-std=legacy"]
LINK_FLAGS = ["-static"]

# Where MSYS2 puts gfortran on Windows, checked when gfortran is not on PATH.
_WINDOWS_CANDIDATES = [
    r"C:\msys64\ucrt64\bin\gfortran.exe",
    r"C:\msys64\mingw64\bin\gfortran.exe",
]


class BuildError(RuntimeError):
    pass


def find_gfortran() -> Path:
    """Locate gfortran: $FC, then PATH, then the usual MSYS2 locations."""
    candidates = [os.environ.get("FC"), shutil.which("gfortran")]
    if sys.platform == "win32":
        candidates += _WINDOWS_CANDIDATES
    for c in candidates:
        if c and Path(c).is_file():
            return Path(c)
    raise BuildError(
        "gfortran not found. Set FC to its path or put it on PATH "
        "(on Windows: MSYS2 package mingw-w64-ucrt-x86_64-gcc-fortran)."
    )


def makefile_sources(source_dir: Path) -> tuple[list[str], list[str]]:
    """Return (SRCS1, SRCS2) as listed in source/makefile."""
    text = (source_dir / "makefile").read_text(encoding="latin-1")
    text = text.replace("\\\n", " ")
    lists = {}
    for name in ("SRCS1", "SRCS2"):
        m = re.search(rf"^{name}\s*=(.*)$", text, re.MULTILINE)
        if not m:
            raise BuildError(f"{name} not found in {source_dir / 'makefile'}")
        lists[name] = m.group(1).split()
    return lists["SRCS1"], lists["SRCS2"]


def _compiler_env(fc: Path) -> dict:
    # gfortran needs its own bin directory on PATH to find as/ld and DLLs.
    env = dict(os.environ)
    env["PATH"] = str(fc.parent) + os.pathsep + env.get("PATH", "")
    return env


def build(source_dir: str | Path, out_dir: str | Path, jobs: int | None = None,
          fc: str | Path | None = None) -> Path:
    """Compile the sources in `source_dir` into `out_dir`; return the exe path."""
    source_dir = Path(source_dir).resolve()
    out_dir = Path(out_dir).resolve()
    obj_dir = out_dir / "obj"
    obj_dir.mkdir(parents=True, exist_ok=True)
    fc = Path(fc) if fc else find_gfortran()
    env = _compiler_env(fc)
    srcs1, srcs2 = makefile_sources(source_dir)

    def compile_one(src: str, flags: list[str]) -> Path:
        obj = obj_dir / (Path(src).stem + ".o")
        cmd = [str(fc), *flags, "-J", str(obj_dir), "-c", src, "-o", str(obj)]
        p = subprocess.run(cmd, cwd=source_dir, env=env,
                           capture_output=True, text=True)
        if p.returncode != 0:
            raise BuildError(f"compiling {src} failed:\n{p.stdout}{p.stderr}")
        return obj

    # .f95 files may define modules used elsewhere, so compile them first and
    # in makefile order; the fixed-form files are independent of each other.
    objs = [compile_one(s, F95_FLAGS) for s in srcs1]
    with ThreadPoolExecutor(max_workers=jobs or os.cpu_count()) as pool:
        objs += list(pool.map(lambda s: compile_one(s, FOR_FLAGS), srcs2))

    exe = out_dir / ("OpenSES.exe" if sys.platform == "win32" else "OpenSES")
    cmd = [str(fc), "-o", str(exe), *map(str, objs), *LINK_FLAGS]
    p = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if p.returncode != 0:
        raise BuildError(f"linking failed:\n{p.stdout}{p.stderr}")
    return exe
