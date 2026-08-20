import math
import unittest

from core.pipeline import IndelSummary
from web.backend.serialize import jsonable


class TestJsonable(unittest.TestCase):
    def test_nan_and_inf_become_none(self):
        self.assertIsNone(jsonable(float("nan")))
        self.assertIsNone(jsonable(float("inf")))
        self.assertEqual(jsonable(12.5), 12.5)

    def test_dataclass_nested_nan(self):
        row = IndelSummary(
            sample="a",
            guide="g",
            amplicon="amp",
            n_reads_with_size_call=0,
            wt=0,
            edited=0,
            pct_editing=math.nan,
            insertions=0,
            deletions=0,
            in_frame=0,
            frameshift=0,
            pct_in_frame_of_edited=math.nan,
        )
        data = jsonable(row)
        self.assertIsNone(data["pct_editing"])
        self.assertIsNone(data["pct_in_frame_of_edited"])
        self.assertEqual(data["sample"], "a")
        self.assertEqual(data["guide"], "g")
