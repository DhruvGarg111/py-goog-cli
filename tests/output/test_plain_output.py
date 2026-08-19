from pygog.output.plain_output import print_plain


def test_print_plain_empty(capsys):
    print_plain([])
    assert capsys.readouterr().out == ""


def test_print_plain_empty_with_columns(capsys):
    print_plain([], columns=["id", "name"])
    assert capsys.readouterr().out == ""


def test_print_plain_basic(capsys):
    data = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
    print_plain(data)
    assert capsys.readouterr().out == "name\tage\nAlice\t30\nBob\t25\n"


def test_print_plain_no_header(capsys):
    data = [{"name": "Alice", "age": 30}]
    print_plain(data, header=False)
    assert capsys.readouterr().out == "Alice\t30\n"


def test_print_plain_custom_columns(capsys):
    data = [{"name": "Alice", "age": 30, "city": "NYC"}]
    print_plain(data, columns=["name", "city"])
    assert capsys.readouterr().out == "name\tcity\nAlice\tNYC\n"


def test_print_plain_missing_key(capsys):
    data = [{"name": "Alice"}, {"name": "Bob", "age": 25}]
    print_plain(data, columns=["name", "age"])
    assert capsys.readouterr().out == "name\tage\nAlice\t\nBob\t25\n"


def test_print_plain_escape_chars(capsys):
    data = [{"note": "line1\nline2\ttab"}]
    print_plain(data, header=False)
    assert capsys.readouterr().out == "line1 line2 tab\n"


def test_print_plain_non_string_values(capsys):
    data = [{"val": 123, "active": True, "none": None}]
    print_plain(data, header=False)
    assert capsys.readouterr().out == "123\tTrue\t\n"


def test_print_plain_null_optional_values_are_empty_cells(capsys):
    print_plain([{"id": "event-1", "location": None}], columns=["id", "location"])

    assert capsys.readouterr().out == "id\tlocation\nevent-1\t\n"


def test_print_plain_generator_columns(capsys):
    data = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
    columns = (column for column in ["name", "age"])
    print_plain(data, columns=columns)
    assert capsys.readouterr().out == "name\tage\nAlice\t30\nBob\t25\n"
