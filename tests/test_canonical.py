from __future__ import annotations

import unittest

from znak_orient.canonical import canonical_json_bytes, normalize_value


class CanonicalDictionaryKeyTests(unittest.TestCase):
    def test_whitespace_normalized_key_collision_is_rejected_regardless_of_order(self):
        for value in (
            {"key": 1, " key ": 2},
            {" key ": 2, "key": 1},
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(TypeError, "keys collide after canonical normalization"):
                    canonical_json_bytes(value)

    def test_unicode_normalized_key_collision_is_rejected(self):
        with self.assertRaisesRegex(TypeError, "keys collide after canonical normalization"):
            canonical_json_bytes({"\u00e9": 1, "e\u0301": 2})

    def test_nested_normalized_key_collision_is_rejected(self):
        with self.assertRaisesRegex(TypeError, "keys collide after canonical normalization"):
            normalize_value({"outer": {"subject": 1, " subject ": 2}})

    def test_distinct_keys_retain_existing_normalization_and_canonical_order(self):
        self.assertEqual(b'{"a":1,"b":2}', canonical_json_bytes({" b ": 2, "a": 1}))


if __name__ == "__main__":
    unittest.main()
