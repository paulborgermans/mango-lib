import importlib
import sys
import types

import pytest


@pytest.fixture
def query_module(monkeypatch):
    irods_module = types.ModuleType("irods")
    irods_session_module = types.ModuleType("irods.session")

    class FakeIRODSSession:
        pass

    irods_session_module.iRODSSession = FakeIRODSSession
    monkeypatch.setitem(sys.modules, "irods", irods_module)
    monkeypatch.setitem(sys.modules, "irods.session", irods_session_module)

    sys.modules.pop("mango_lib.irods.query", None)
    return importlib.import_module("mango_lib.irods.query")


def test_genquery2_select_dict_builds_select_and_transforms_results(query_module):
    class DummySession:
        def __init__(self):
            self.query_string = None

        def genquery2(self, query_string):
            self.query_string = query_string
            return [["1", "alice"], ["2", "bob"]]

    session = DummySession()

    result = query_module.genquery2_select_dict(
        session,
        {"id": int, "name": str.upper},
        "WHERE DATA_NAME like '%.txt'",
    )

    assert session.query_string == "SELECT id, name WHERE DATA_NAME like '%.txt'"
    assert result == [
        {"id": 1, "name": "ALICE"},
        {"id": 2, "name": "BOB"},
    ]


def test_genquery2_select_dict_uses_query_string_as_is_when_generate_select_is_false(
    query_module,
):
    class DummySession:
        def __init__(self):
            self.query_string = None

        def genquery2(self, query_string):
            self.query_string = query_string
            return [["3"]]

    session = DummySession()
    query_string = "select count(DATA_ID) where DATA_PATH like '/zone/home%'"

    result = query_module.genquery2_select_dict(
        session,
        {"count": int},
        query_string,
        generate_select=False,
    )

    assert session.query_string == query_string
    assert result == [{"count": 3}]


@pytest.mark.parametrize("q_result", [[], None])
def test_genquery2_select_dict_returns_empty_list_for_empty_results(query_module, q_result):
    class DummySession:
        def genquery2(self, query_string):
            return q_result

    result = query_module.genquery2_select_dict(
        DummySession(),
        {"id": int},
        "WHERE COLL_NAME = '/tempZone/home'",
    )

    assert result == []


def test_genquery2_select_dict_raises_value_error_on_column_count_mismatch(query_module):
    class DummySession:
        def genquery2(self, query_string):
            return [["1", "alice"]]

    with pytest.raises(ValueError):
        query_module.genquery2_select_dict(
            DummySession(),
            {"id": int},
            "WHERE USER_NAME = 'alice'",
        )


def test_genquery2_select_dict_applies_transformers_by_column_position(query_module):
    class DummySession:
        def genquery2(self, query_string):
            return [["7", "3.14", "mixedCase"]]

    result = query_module.genquery2_select_dict(
        DummySession(),
        {
            "count": int,
            "ratio": float,
            "label": lambda value: value.lower(),
        },
        "WHERE META_ATTR_NAME = 'example'",
    )

    assert result == [
        {
            "count": 7,
            "ratio": 3.14,
            "label": "mixedcase",
        }
    ]