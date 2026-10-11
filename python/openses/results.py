"""Read OpenSES JSON output into pandas tables.

The JSON file is a list: an "info" object, then one object per print time
("pit") holding train, section, segment and subsegment records, and (from
this fork on) a closing "run_status" object.  `Results` flattens the pits
into one long table per record type, with the print time as a column, so
the data can be filtered, pivoted, plotted or exported directly.

Files written by OpenSES 4.3ALPHA and earlier are often not valid JSON:
when the simulation ends without an environmental control estimate the
list is never closed.  `load_json` repairs that case.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

TABLES = {
    "trains": "train_data",
    "sections": "section_data",
    "segments": "segment_data",
    "subsegments": "subsegment_data",
}

# Units of the JSON fields as written by JSONPIT.FOR (US customary / IP),
# taken from the matching column headers in PRINT.FOR and RECORD.TXT.
UNITS_IP = {
    "time": "s",
    # trains (PRINT.FOR formats 31 and 641)
    "position": "ft", "velocity": "mph", "acceleration": "mph/s",
    "total_drag": "lbf", "air_drag": "lbf", "tractive_effort": "lbf/motor",
    "drag_coefficient": "-", "motor_current": "A", "line_current": "A",
    "flywheel_speed": "rpm",
    "accel_grid_temperature": "degF", "decel_grid_temperature": "degF",
    "heat_generated": "BTU/s-ft", "heat_rejected": "BTU/s-ft",
    "aux_power": "W/train", "propulsion_power": "W/train",
    "regeneration_power": "W/train", "flywheel_power": "W/train",
    "accel_grid_heat_in": "BTU/s-train", "decel_grid_heat_in": "BTU/s-train",
    "rolling_resistance_heat": "BTU/s-train",
    "propulsion_heat_released": "BTU/s-ft",
    "aux_heat_released_sensible": "BTU/s-ft",
    "aux_heat_released_latent": "BTU/s-ft",
    "passengers": "-",
    # sections / segments
    "airflow_rate": "cfm", "buoyancy": "in. WG", "pressure_change": "in. WG",
    "air_velocity": "fpm", "reynolds_number": "-",
    # subsegments
    "air_temperature": "degF", "wall_temperature": "degF",
    "humidity_ratio": "lb/lb", "heat_transfer_coeff": "BTU/ft2-s-degF",
    "sensible_heat_load": "BTU/s", "latent_heat_load": "BTU/s",
    "qwalss": "BTU/s-ft2", "qradss": "BTU/s",
    "sensible_ac": "BTU/s", "latent_ac": "BTU/s",
}


class OutputFormatError(ValueError):
    pass


def load_json(path: str | Path) -> list:
    """Load an OpenSES JSON file, repairing an unterminated pit list."""
    text = Path(path).read_text(encoding="latin-1")
    return loads(text)


def loads(text: str) -> list:
    if not text.strip():
        raise OutputFormatError("empty JSON output (run stopped before input verification ended)")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Legacy files end with "}," after the last pit and lack the closing "]".
    repaired = text.rstrip().rstrip(",") + "\n]"
    try:
        return json.loads(repaired)
    except json.JSONDecodeError as e:
        raise OutputFormatError(f"not an OpenSES JSON file: {e}") from None


def _split_id(series: pd.Series, names: list[str]) -> pd.DataFrame:
    """Split ids like "3 -103 -  1" into integer columns."""
    parts = series.str.split("-", expand=True)
    parts.columns = names[: parts.shape[1]]
    return parts.apply(lambda c: pd.to_numeric(c.str.strip()))


@dataclass
class Results:
    info: dict
    pits: list[dict] = field(repr=False)
    run_status: dict | None = None
    source: Path | None = None
    _cache: dict = field(default_factory=dict, repr=False)

    @classmethod
    def read(cls, path: str | Path) -> "Results":
        data = load_json(path)
        info, pits, status = {}, [], None
        for item in data:
            if "info" in item:
                info = item["info"]
            elif "pit" in item:
                pits.append(item)
            elif "run_status" in item:
                status = item["run_status"]
        return cls(info, pits, status, Path(path))

    @property
    def times(self) -> list[float]:
        return [p["pit"] for p in self.pits]

    def table(self, name: str) -> pd.DataFrame:
        """One long table over all print times: 'trains', 'sections',
        'segments' or 'subsegments'."""
        if name not in TABLES:
            raise KeyError(f"unknown table {name!r}; choose from {list(TABLES)}")
        if name not in self._cache:
            key = TABLES[name]
            rows = [
                {"pit_index": i, "time": p["pit"], **rec}
                for i, p in enumerate(self.pits)
                for rec in p.get(key, [])
            ]
            df = pd.DataFrame.from_records(rows)
            if not df.empty:
                if name == "segments":
                    ids = _split_id(df.pop("segment_id"), ["section", "segment"])
                    df = pd.concat([df.iloc[:, :2], ids, df.iloc[:, 2:]], axis=1)
                elif name == "subsegments":
                    ids = _split_id(df.pop("subsegment_id"),
                                    ["section", "segment", "subsegment"])
                    df = pd.concat([df.iloc[:, :2], ids, df.iloc[:, 2:]], axis=1)
                elif name == "sections":
                    df = df.rename(columns={"section_id": "section"})
            self._cache[name] = df
        return self._cache[name]

    @property
    def trains(self) -> pd.DataFrame:
        return self.table("trains")

    @property
    def sections(self) -> pd.DataFrame:
        return self.table("sections")

    @property
    def segments(self) -> pd.DataFrame:
        return self.table("segments")

    @property
    def subsegments(self) -> pd.DataFrame:
        return self.table("subsegments")

    def timeseries(self, table: str, value: str, by: str | list[str]) -> pd.DataFrame:
        """Wide table: one row per print time, one column per item.

        Example: res.timeseries("sections", "airflow_rate", "section")
        """
        df = self.table(table)
        return df.pivot_table(index="time", columns=by, values=value,
                              aggfunc="last")

    # ---- export -----------------------------------------------------------

    def to_csv(self, folder: str | Path) -> list[Path]:
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        written = []
        for name in TABLES:
            df = self.table(name)
            if not df.empty:
                p = folder / f"{name}.csv"
                df.to_csv(p, index=False)
                written.append(p)
        return written

    def to_excel(self, path: str | Path) -> Path:
        path = Path(path)
        limit = 1_048_575  # Excel rows minus the header row
        with pd.ExcelWriter(path) as xl:
            pd.DataFrame(
                [{"key": k, "value": v} for k, v in self.info.items()]
                + [{"key": f"run_status.{k}", "value": v}
                   for k, v in (self.run_status or {}).items()]
            ).to_excel(xl, sheet_name="info", index=False)
            for name in TABLES:
                df = self.table(name)
                if df.empty:
                    continue
                for n, start in enumerate(range(0, len(df), limit)):
                    sheet = name if n == 0 else f"{name}_{n + 1}"
                    df.iloc[start:start + limit].to_excel(
                        xl, sheet_name=sheet, index=False)
            pd.DataFrame(
                [{"column": k, "unit": v} for k, v in UNITS_IP.items()]
            ).to_excel(xl, sheet_name="units", index=False)
        return path

    def to_parquet(self, folder: str | Path) -> list[Path]:
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        written = []
        for name in TABLES:
            df = self.table(name)
            if not df.empty:
                p = folder / f"{name}.parquet"
                df.to_parquet(p, index=False)
                written.append(p)
        return written


def read(path: str | Path) -> Results:
    return Results.read(path)
