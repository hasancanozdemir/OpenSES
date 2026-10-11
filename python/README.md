# openses (Python tools)

Tools to build and run OpenSES and to work with its output as tables.
They never change what OpenSES computes: the solver is the Fortran code
in `source/`, and the A/B test below checks that every change keeps its
results identical.

## Setup

* gfortran. On Windows install [MSYS2](https://www.msys2.org) and run
  `pacman -S mingw-w64-ucrt-x86_64-gcc-fortran`; the tools find it in
  `C:\msys64\ucrt64\bin` without further setup. On Linux use the
  distribution's `gfortran` package. Or set `FC` to the compiler path.
* Python 3.10+ with pandas; openpyxl for Excel export, pyarrow for Parquet.

Run the commands from this `python/` folder (or `pip install -e python`
from the repository root to get an `openses` command).

## Command line

```
python -m openses build                       # compile source/ into bin/
python -m openses run case.inp                # outputs next to case.inp
python -m openses run a.inp b.inp c.inp --out runs --export xlsx
python -m openses info case.JSON              # what is in an output file
python -m openses export case.JSON --to csv   # or xlsx, parquet
python -m openses abtest                      # prove results are unchanged
```

`run` with several inputs runs them in parallel, one subfolder each, and
reports every exit code (100 = completed, 99 = input verified only).

## From Python

```python
import openses

res = openses.read("inferno.JSON")
res.subsegments        # one row per subsegment and print time
res.sections           # airflow per section and print time
res.trains, res.segments
res.run_status         # exit code and versions, written at program end

# Airflow of every section over time, ready to plot
res.timeseries("sections", "airflow_rate", "section").plot()

# Hottest subsegment at the last print time
s = res.subsegments
last = s[s.time == s.time.max()]
last.nlargest(5, "air_temperature")[["section", "segment", "subsegment", "air_temperature"]]
```

Values are in the units OpenSES writes (US customary); see
`openses.results.UNITS_IP` or the `units` sheet of an Excel export.

## The A/B test

`python -m openses.abtest [--ref REV]` extracts `source/` of a git
revision (default `baseline-4.3alpha`: upstream Develop with only the
compile fixes), builds it and the working tree with the same compiler,
runs every case in `../tests/cases.txt` with both, and fails unless

* exit codes match (or match `exit=N` given for the case),
* `.OUT` and `.RST` files are identical apart from run timestamps,
* every value in the reference JSON is present and equal in the new one.

CI runs it on every push.
