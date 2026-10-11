"""Command line interface: `openses build | run | export | info | abtest`."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .build import build
from .results import Results, TABLES
from .runner import EXIT_MEANINGS, run_case, run_many

REPO = Path(__file__).resolve().parents[2]
DEFAULT_BIN = REPO / "bin"


def default_exe() -> Path:
    env = os.environ.get("OPENSES_EXE")
    if env:
        return Path(env)
    exe = DEFAULT_BIN / ("OpenSES.exe" if sys.platform == "win32" else "OpenSES")
    if not exe.exists():
        sys.exit(f"no OpenSES executable at {exe}; run `openses build` first "
                 "or set OPENSES_EXE")
    return exe


def export(json_path: Path, fmt: str, dest: Path | None) -> list[Path]:
    res = Results.read(json_path)
    if fmt == "xlsx":
        return [res.to_excel(dest or json_path.with_suffix(".xlsx"))]
    folder = dest or json_path.with_name(json_path.stem + f"_{fmt}")
    return res.to_csv(folder) if fmt == "csv" else res.to_parquet(folder)


def cmd_build(a):
    exe = build(a.source, a.out, jobs=a.jobs)
    print(exe)


def cmd_run(a):
    exe = a.exe or default_exe()
    inputs = [Path(p) for p in a.inputs]
    if len(inputs) == 1 and not a.out:
        # Single case: write outputs next to the input, like OpenSES itself.
        results = [run_case(exe, inputs[0], inputs[0].parent)]
    else:
        out = Path(a.out) if a.out else Path.cwd() / "openses-runs"
        results = run_many(exe, inputs, out, jobs=a.jobs)
    failed = 0
    for r in results:
        ok = r.returncode in (99, 100)
        failed += not ok
        print(f"{'ok  ' if ok else 'FAIL'}  {r.input.name:30} exit {r.returncode:4}  "
              f"{r.seconds:6.2f}s  {r.status}  -> {r.workdir}")
        if a.export and r.json and r.json.stat().st_size:
            for p in export(r.json, a.export, None):
                print(f"      exported {p}")
    return 1 if failed else 0


def cmd_export(a):
    for p in export(Path(a.json), a.to, Path(a.out) if a.out else None):
        print(p)


def cmd_info(a):
    res = Results.read(a.json)
    print(f"file:        {res.source}")
    for k, v in res.info.items():
        print(f"info.{k + ':':24} {v}")
    if res.run_status:
        code = res.run_status.get("exit_code")
        print(f"run status:  exit {code} ({EXIT_MEANINGS.get(code, 'input error')})")
    else:
        print("run status:  not recorded (file written by OpenSES 4.3ALPHA or earlier)")
    t = res.times
    if t:
        print(f"print times: {len(t)} ({t[0]:g} s to {t[-1]:g} s)")
    for name in TABLES:
        df = res.table(name)
        print(f"{name + ':':13}{len(df):8} rows, {df.shape[1]} columns")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="openses", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="compile the Fortran sources with gfortran")
    b.add_argument("--source", type=Path, default=REPO / "source")
    b.add_argument("--out", type=Path, default=DEFAULT_BIN)
    b.add_argument("--jobs", type=int)
    b.set_defaults(func=cmd_build)

    r = sub.add_parser("run", help="run one or more input files")
    r.add_argument("inputs", nargs="+")
    r.add_argument("--exe", type=Path, help="OpenSES executable (default: bin/ or $OPENSES_EXE)")
    r.add_argument("--out", help="folder for the runs (one subfolder per case)")
    r.add_argument("--jobs", type=int, help="parallel runs (default: CPU count)")
    r.add_argument("--export", choices=["xlsx", "csv", "parquet"],
                   help="also convert each JSON output")
    r.set_defaults(func=cmd_run)

    e = sub.add_parser("export", help="convert a JSON output to tables")
    e.add_argument("json")
    e.add_argument("--to", choices=["xlsx", "csv", "parquet"], default="xlsx")
    e.add_argument("--out", help="output file (xlsx) or folder (csv, parquet)")
    e.set_defaults(func=cmd_export)

    i = sub.add_parser("info", help="summarise a JSON output")
    i.add_argument("json")
    i.set_defaults(func=cmd_info)

    t = sub.add_parser("abtest", help="prove outputs are unchanged against a git revision",
                       add_help=False)
    t.set_defaults(func=None)

    args, rest = ap.parse_known_args(argv)
    if args.cmd == "abtest":
        from .abtest import main as ab_main
        return ab_main(rest)
    if rest:
        ap.error(f"unrecognized arguments: {' '.join(rest)}")
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
