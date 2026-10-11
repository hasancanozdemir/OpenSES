"""Python tools around the OpenSES (Subway Environment Simulation) solver.

These tools only prepare inputs, run the Fortran program and read its
outputs; the computation itself is the unchanged Fortran code.
"""

from .build import build, find_gfortran
from .results import Results, read
from .runner import RunResult, run_case, run_many

__all__ = ["build", "find_gfortran", "read", "Results", "run_case",
           "run_many", "RunResult"]
__version__ = "0.1.0"
