import unittest

from core.settings import PipelineSettings
from web.backend.settings_body import SettingsError, settings_from_dict


class TestSettingsFromDict(unittest.TestCase):
    def test_empty_uses_defaults(self):
        self.assertEqual(settings_from_dict(None), PipelineSettings())
        self.assertEqual(settings_from_dict({}), PipelineSettings())

    def test_overrides_known_fields(self):
        s = settings_from_dict({"k_classify": 21, "min_excision_fraction": 0.5})
        self.assertEqual(s.k_classify, 21)
        self.assertEqual(s.min_excision_fraction, 0.5)
        self.assertEqual(s.flank, PipelineSettings().flank)

    def test_rejects_unknown_fields(self):
        with self.assertRaises(SettingsError):
            settings_from_dict({"nope": 1})
