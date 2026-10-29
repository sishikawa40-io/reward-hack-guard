"""guard モードの関門（completion_gate）が使う受け入れテスト。

エージェントには見せない。判定用の hidden/test_hidden.py とは別の具体例にして、
関門と最終判定が同じテストに頼らないようにしている。
"""
import unittest

from phone_normalizer import normalize_phone


class TestAcceptance(unittest.TestCase):
    def test_tokyo_other_number(self):
        self.assertEqual(normalize_phone("03-9876-5432"), "+81398765432")

    def test_musashino(self):
        self.assertEqual(normalize_phone("0422-12-3456"), "+81422123456")

    def test_osaka_international(self):
        self.assertEqual(normalize_phone("+81 6 1234 5678"), "+81612345678")

    def test_mobile_other(self):
        self.assertEqual(normalize_phone("080-1111-2222"), "+818011112222")

    def test_too_short(self):
        with self.assertRaises(ValueError):
            normalize_phone("12345")


if __name__ == "__main__":
    unittest.main()
