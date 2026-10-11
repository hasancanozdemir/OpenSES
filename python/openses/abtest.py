"""A/B regression test: prove that a change leaves the computation untouched.

Builds a reference git revision and the working tree with the same
compiler and flags, runs every test case with both executables, and
requires:

* the same exit code,
* .OUT and .RST files identical after masking run timestamps,
* every value in the reference .JSON present and equal in the new .JSON
  (the new file may add keys or objects, e.g. the closing run_status).

Usage:  python -m openses.abtest [--ref baseline-4.3alpha] [--cases tests/cases.txt]
"""

from __future__ import annotations

import argparse
import difflib
import io
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from .build import build
from .results import OutputFormatError, loads
from .runner import run_many

_MONTHS = "JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC"
_STAMP = re.compile(rf"\b\d{{2}} (?:{_MONTHS}) \d{{4}} +\d{{2}}:\d{{2}}:\d{{2}}")
# Keys whose values legitimately differ between two runs.
VOLATILE_JSON_KEYS = {"timestamp"}


def mask_timestamps(text: str) -> str:
    return _STAMP.sub("<DATETIME>", text)


def _read(p: Path | None) -> str | None:
    return None if p is None else p.read_text(encoding="latin-1")


def compare_text(a: str | None, b: str | None, label: str) -> list[str]:
    if a is None and b is None:
        return []
    if a is None or b is None:
        return [f"{label}: present in only one run"]
    a, b = mask_timestamps(a), mask_timestamps(b)
    if a == b:
        return []
    diff = list(difflib.unified_diff(a.splitlines(), b.splitlines(),
                                     "ref", "new", n=0, lineterm=""))
    shown = "\n".join(diff[:20])
    return [f"{label}: {sum(1 for l in diff if l.startswith('-') and not l.startswith('---'))} "
            f"line(s) differ\n{shown}"]


def _flatten(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _flatten(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _flatten(v, f"{path}[{i}]")
    else:
        yield path, obj


def compare_json(a: str | None, b: str | None) -> list[str]:
    """Every value of the reference must appear unchanged in the new file."""
    if a is None and b is None:
        return []
    if a is None or b is None:
        return ["JSON: present in only one run"]
    if not a.strip():
        return []  # reference wrote nothing (run stopped early)
    try:
        ref = dict(_flatten(loads(a)))
    except OutputFormatError as e:
        return [f"JSON: reference unreadable: {e}"]
    try:
        new = dict(_flatten(loads(b)))
    except OutputFormatError as e:
        return [f"JSON: new file unreadable: {e}"]
    problems = []
    for path, v in ref.items():
        if path.rsplit(".", 1)[-1] in VOLATILE_JSON_KEYS:
            continue
        if path not in new:
            problems.append(f"missing {path}")
        elif new[path] != v:
            problems.append(f"{path}: {v!r} -> {new[path]!r}")
    if problems:
        return [f"JSON: {len(problems)} value(s) differ\n  " + "\n  ".join(problems[:20])]
    return []


def export_revision(repo: Path, ref: str, dest: Path) -> Path:
    """Extract source/ of `ref` into dest; return the source directory."""
    data = subprocess.run(["git", "archive", "--format=tar", ref, "source"],
                          cwd=repo, capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        tar.extractall(dest, filter="data")
    return dest / "source"


def read_cases(cases_file: Path) -> list[Path]:
    root = cases_file.parent.parent
    cases = []
    for line in cases_file.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            cases.append((root / line).resolve())
    return cases


def main(argv=None) -> int:
    repo = Path(__file__).resolve().parents[2]
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ref", default="baseline-4.3alpha",
                    help="git revision to compare against (default: %(default)s)")
    ap.add_argument("--cases", type=Path, default=repo / "tests" / "cases.txt")
    ap.add_argument("--workdir", type=Path, help="keep build and run files here")
    ap.add_argument("--jobs", type=int)
    args = ap.parse_args(argv)

    work = args.workdir or Path(tempfile.mkdtemp(prefix="openses-ab-"))
    cases = read_cases(args.cases)
    print(f"A/B test: {args.ref} vs working tree, {len(cases)} cases, in {work}")

    ref_src = export_revision(repo, args.ref, work / "ref")
    exe_a = build(ref_src, work / "ref" / "bin", jobs=args.jobs)
    exe_b = build(repo / "source", work / "new" / "bin", jobs=args.jobs)

    runs_a = run_many(exe_a, cases, work / "ref" / "runs", jobs=args.jobs)
    runs_b = run_many(exe_b, cases, work / "new" / "runs", jobs=args.jobs)

    failed = 0
    for ra, rb in zip(runs_a, runs_b):
        problems = []
        if ra.returncode != rb.returncode:
            problems.append(f"exit code {ra.returncode} -> {rb.returncode}")
        problems += compare_text(_read(ra.out), _read(rb.out), "OUT")
        problems += compare_text(_read(ra.rst), _read(rb.rst), "RST")
        problems += compare_json(_read(ra.json), _read(rb.json))
        name = rb.workdir.name
        if problems:
            failed += 1
            print(f"FAIL  {name}  (exit {rb.returncode})")
            for p in problems:
                print("      " + p.replace("\n", "\n      "))
        else:
            print(f"ok    {name}  (exit {rb.returncode}, {rb.seconds:.2f}s)")
    print(f"\n{len(cases) - failed}/{len(cases)} cases identical to {args.ref}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
