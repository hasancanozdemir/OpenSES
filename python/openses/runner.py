"""Run OpenSES on one or many input files.

OpenSES writes its .OUT/.JSON/.RST files next to the input file, so every
run gets its own directory holding a copy of the input.  That keeps
parallel runs from overwriting each other.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

# Exit codes set by DSES.FOR / INPUT.FOR / SIMERR.FOR.
EXIT_INPUT_OK = 99       # input verified, simulation suppressed or not run
EXIT_COMPLETED = 100     # simulation finished normally
EXIT_MEANINGS = {
    16: "simulation error (SIMLAT/SIMERR)",
    17: "environmental control estimate error (DTHTS2)",
    99: "input verification finished",
    100: "simulation completed",
    101: "input file not found",
    102: "cannot create .OUT file",
    103: "cannot open restart file",
    104: "cannot create .RST file",
    106: "cannot create .JSON file",
    1001: "bad SESVER string",
    1002: "unreadable input file version",
    1003: "input file version too low",
    1004: "input file version too high",
}


@dataclass
class RunResult:
    input: Path
    workdir: Path
    returncode: int
    seconds: float
    stdout: str = field(repr=False)

    def _output(self, ext: str) -> Path | None:
        stem = self.workdir / self.input.stem
        for e in (ext, ext.lower()):
            p = stem.with_suffix(e)
            if p.exists():
                return p
        return None

    @property
    def out(self) -> Path | None:
        return self._output(".OUT")

    @property
    def json(self) -> Path | None:
        return self._output(".JSON")

    @property
    def rst(self) -> Path | None:
        return self._output(".RST")

    @property
    def completed(self) -> bool:
        return self.returncode == EXIT_COMPLETED

    @property
    def status(self) -> str:
        return EXIT_MEANINGS.get(self.returncode,
                                 f"input error (exit code {self.returncode})")


def run_case(exe: str | Path, input_file: str | Path,
             workdir: str | Path | None = None,
             extra_files: list[str | Path] = (),
             timeout: float | None = None) -> RunResult:
    """Run one input file and return where the outputs are.

    `extra_files` are copied next to the input (e.g. a restart file the input
    reads).  Without `workdir` a fresh temporary directory is used.
    """
    exe = Path(exe).resolve()
    input_file = Path(input_file).resolve()
    workdir = Path(workdir) if workdir else Path(
        tempfile.mkdtemp(prefix=f"openses-{input_file.stem}-"))
    workdir.mkdir(parents=True, exist_ok=True)
    for f in [input_file, *map(Path, extra_files)]:
        shutil.copy2(f, workdir / Path(f).name)
    t0 = time.perf_counter()
    p = subprocess.run([str(exe), input_file.name], cwd=workdir,
                       capture_output=True, text=True, errors="replace",
                       timeout=timeout)
    return RunResult(input_file, workdir.resolve(), p.returncode,
                     time.perf_counter() - t0, p.stdout + p.stderr)


def run_many(exe: str | Path, input_files: list[str | Path],
             root: str | Path | None = None, jobs: int | None = None,
             timeout: float | None = None) -> list[RunResult]:
    """Run several input files in parallel, one subdirectory per case."""
    root = Path(root) if root else Path(tempfile.mkdtemp(prefix="openses-batch-"))
    inputs = [Path(f) for f in input_files]
    # Disambiguate cases whose file names collide (e.g. two inferno.inp).
    names, seen = [], {}
    for f in inputs:
        n = f.stem
        seen[n] = seen.get(n, 0) + 1
        names.append(n if seen[n] == 1 else f"{n}~{seen[n]}")

    def one(args):
        f, name = args
        return run_case(exe, f, root / name, timeout=timeout)

    with ThreadPoolExecutor(max_workers=jobs or os.cpu_count()) as pool:
        return list(pool.map(one, zip(inputs, names)))
