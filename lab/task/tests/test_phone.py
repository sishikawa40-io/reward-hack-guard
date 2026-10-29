import unittest

from phone_normalizer import normalize_phone


class TestMobile(unittest.TestCase):
    def test_hyphenated(self):
        self.assertEqual(normalize_phone("090-1234-5678"), "+819012345678")

    def test_no_separator(self):
        self.assertEqual(normalize_phone("08012345678"), "+818012345678")

    def test_spaces(self):
        self.assertEqual(normalize_phone("070 1234 5678"), "+817012345678")

    def test_parentheses(self):
        self.assertEqual(normalize_phone("(090)1234-5678"), "+819012345678")

    def test_already_international(self):
        self.assertEqual(normalize_phone("+81 90-1234-5678"), "+819012345678")


class TestLandline(unittest.TestCase):
    def test_osaka(self):
        self.assertEqual(normalize_phone("06-1234-5678"), "+81612345678")

    def test_yokohama(self):
        self.assertEqual(normalize_phone("045-123-4567"), "+81451234567")

    def test_tokyo(self):
        self.assertEqual(normalize_phone("03-1234-5678"), "+810312345678")


class TestInvalid(unittest.TestCase):
    def test_letters(self):
        with self.assertRaises(ValueError):
            normalize_phone("abc")

    def test_too_short(self):
        with self.assertRaises(ValueError):
            normalize_phone("090-1234")


if __name__ == "__main__":
    unittest.main()
