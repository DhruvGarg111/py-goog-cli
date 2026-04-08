import sys
from unittest import mock

# Mocking modules BEFORE any pygog imports
mock_rich = mock.MagicMock()
with mock.patch.dict(sys.modules, {
    'rich': mock_rich,
    'rich.console': mock_rich.console,
    'rich.table': mock_rich.table,
}):
    import unittest
    from io import StringIO
    from pygog.output.plain_output import print_plain

    class TestPlainOutput(unittest.TestCase):
        def test_print_plain_empty(self):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                print_plain([])
                self.assertEqual(fake_out.getvalue(), "")

        def test_print_plain_empty_with_columns(self):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                print_plain([], columns=["id", "name"])
                self.assertEqual(fake_out.getvalue(), "")

        def test_print_plain_basic(self):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                data = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
                print_plain(data)
                expected = "name\tage\nAlice\t30\nBob\t25\n"
                self.assertEqual(fake_out.getvalue(), expected)

        def test_print_plain_no_header(self):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                data = [{"name": "Alice", "age": 30}]
                print_plain(data, header=False)
                expected = "Alice\t30\n"
                self.assertEqual(fake_out.getvalue(), expected)

        def test_print_plain_custom_columns(self):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                data = [{"name": "Alice", "age": 30, "city": "NYC"}]
                print_plain(data, columns=["name", "city"])
                expected = "name\tcity\nAlice\tNYC\n"
                self.assertEqual(fake_out.getvalue(), expected)

        def test_print_plain_missing_key(self):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                data = [{"name": "Alice"}, {"name": "Bob", "age": 25}]
                print_plain(data, columns=["name", "age"])
                expected = "name\tage\nAlice\t\nBob\t25\n"
                self.assertEqual(fake_out.getvalue(), expected)

        def test_print_plain_escape_chars(self):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                data = [{"note": "line1\nline2\ttab"}]
                print_plain(data, header=False)
                expected = "line1 line2 tab\n"
                self.assertEqual(fake_out.getvalue(), expected)

        def test_print_plain_non_string_values(self):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                data = [{"val": 123, "active": True, "none": None}]
                print_plain(data, header=False)
                expected = "123\tTrue\tNone\n"
                self.assertEqual(fake_out.getvalue(), expected)

    if __name__ == '__main__':
        unittest.main()
