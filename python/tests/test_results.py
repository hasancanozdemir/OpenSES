import json
import tempfile
import unittest
from pathlib import Path

from openses.abtest import compare_json, compare_text, mask_timestamps
from openses.build import makefile_sources
from openses.results import OutputFormatError, Results, loads

REPO = Path(__file__).resolve().parents[2]
SAMPLES = REPO / "samples" / "inp-version-samples-2023"


class LoadJsonTest(unittest.TestCase):
    def test_unterminated_legacy_file_is_repaired(self):
        # Written by OpenSES 4.3ALPHA: the pit list is never closed.
        text = (SAMPLES / "inferno.JSON").read_text(encoding="latin-1")
        with self.assertRaises(json.JSONDecodeError):
            json.loads(text)
        data = loads(text)
        self.assertIn("info", data[0])
        self.assertTrue(all("pit" in item for item in data[1:]))

    def test_empty_file_is_reported(self):
        with self.assertRaises(OutputFormatError):
            loads("")

    def test_garbage_is_reported(self):
        with self.assertRaises(OutputFormatError):
            loads("[ {not json")

    def test_run_status_object_is_separated(self):
        text = json.dumps([{"info": {"units": "IP"}}, {"pit": 0.0},
                           {"run_status": {"exit_code": 100}}])
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.JSON"
            p.write_text(text)
            res = Results.read(p)
        self.assertEqual(res.run_status, {"exit_code": 100})
        self.assertEqual(res.times, [0.0])


class TablesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = Results.read(SAMPLES / "normal.JSON")

    def test_one_row_per_record_and_print_time(self):
        pits = self.res.pits
        expected = sum(len(p["subsegment_data"]) for p in pits)
        self.assertEqual(len(self.res.subsegments), expected)
        self.assertEqual(self.res.subsegments["time"].nunique(), len(set(self.res.times)))

    def test_ids_are_split_into_integer_columns(self):
        seg = self.res.segments
        self.assertEqual(list(seg.columns[:4]), ["pit_index", "time", "section", "segment"])
        self.assertTrue(str(seg["section"].dtype).startswith("int"))
        sub = self.res.subsegments
        self.assertEqual(list(sub.columns[2:5]), ["section", "segment", "subsegment"])

    def test_values_match_the_json(self):
        first = self.res.pits[1]["section_data"][0]
        row = self.res.sections.query("pit_index == 1").iloc[0]
        self.assertEqual(row["section"], first["section_id"])
        self.assertEqual(row["airflow_rate"], first["airflow_rate"])

    def test_timeseries_is_wide(self):
        ts = self.res.timeseries("sections", "airflow_rate", "section")
        self.assertEqual(ts.shape[1], self.res.sections["section"].nunique())

    def test_csv_export(self):
        with tempfile.TemporaryDirectory() as d:
            written = self.res.to_csv(d)
            self.assertEqual({p.name for p in written},
                             {"trains.csv", "sections.csv", "segments.csv",
                              "subsegments.csv"})


class AbTestHelpersTest(unittest.TestCase):
    def test_timestamps_are_masked(self):
        self.assertEqual(mask_timestamps("12 OCT 2026 00:13:20   SES VER"),
                         "<DATETIME>   SES VER")
        self.assertEqual(mask_timestamps("started at:  23 JAN 2023 14:50:04"),
                         "started at:  <DATETIME>")

    def test_text_difference_is_reported(self):
        self.assertEqual(compare_text("a\n1.0", "a\n1.0", "OUT"), [])
        self.assertTrue(compare_text("a\n1.0", "a\n1.1", "OUT"))

    def test_json_may_gain_keys_but_not_change_values(self):
        ref = json.dumps([{"info": {"timestamp": "x"}}, {"pit": 1.0, "v": 2.0}])
        added = json.dumps([{"info": {"timestamp": "y"}}, {"pit": 1.0, "v": 2.0},
                            {"run_status": {"exit_code": 100}}])
        changed = json.dumps([{"info": {"timestamp": "x"}}, {"pit": 1.0, "v": 2.5}])
        self.assertEqual(compare_json(ref, added), [])
        self.assertTrue(compare_json(ref, changed))


class BuildTest(unittest.TestCase):
    def test_makefile_lists_are_read(self):
        f95, fixed = makefile_sources(REPO / "source")
        self.assertIn("jsonout.f95", f95)
        self.assertIn("SIMLAT.FOR", fixed)
        on_disk = {p.name for p in (REPO / "source").glob("*.FOR")}
        self.assertEqual(set(fixed), on_disk)


if __name__ == "__main__":
    unittest.main()
