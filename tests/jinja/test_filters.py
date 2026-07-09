"""Tests for MangoJinjaExtension template filters.

@todo: Only trivial cases for now, add edge cases
@todo: consider pytest-mock if more advanced features are needed such s patching iRODS session or other objects
"""

import base64
import datetime
from unittest.mock import MagicMock  # part of standard library for simple mocking

import pytest
from jinja2 import Environment

from mango_lib.jinja import MangoJinjaExtension, MangoJinjaUtils


@pytest.fixture
def env() -> Environment:
    """Provide a Jinja2 environment with MangoJinjaExtension registered."""
    return Environment(extensions=[MangoJinjaExtension])


@pytest.fixture
def mock_irods_item():
    """Provide a mock iRODS item with metadata."""
    item = MagicMock()
    meta_single = MagicMock()
    meta_single.value = "single_value"
    meta_single.units = "kg"

    meta_multi_1 = MagicMock()
    meta_multi_1.value = "value1"
    meta_multi_1.units = "unit1"
    meta_multi_2 = MagicMock()
    meta_multi_2.value = "value2"
    meta_multi_2.units = "unit2"

    def get_one(name):
        if name == "single":
            return meta_single
        raise Exception("Not found")

    def get_all(name):
        if name == "multi":
            return [meta_multi_1, meta_multi_2]
        return []

    item.metadata.get_one.side_effect = get_one
    item.metadata.get_all.side_effect = get_all
    return item


def test_get_one_irods_metadata(env, mock_irods_item):
    template = env.from_string("{{ item | get_one_irods_metadata('single') }}")
    assert template.render(item=mock_irods_item) == "single_value"


def test_get_one_irods_metadata_as_tuple(env, mock_irods_item):
    template = env.from_string(
        "{{ item | get_one_irods_metadata('single', as_tuple=True) }}"
    )
    assert template.render(item=mock_irods_item) == "('single_value', 'kg')"


def test_get_one_irods_metadata_default(env, mock_irods_item):
    template = env.from_string(
        "{{ item | get_one_irods_metadata('missing', 'fallback') }}"
    )
    assert template.render(item=mock_irods_item) == "fallback"


def test_get_irods_metadata(env, mock_irods_item):
    template = env.from_string("{{ item | get_irods_metadata('multi') }}")
    assert template.render(item=mock_irods_item) == "['value1', 'value2']"


def test_get_irods_metadata_as_tuple(env, mock_irods_item):
    template = env.from_string(
        "{{ item | get_irods_metadata('multi', as_tuple=True) }}"
    )
    result = template.render(item=mock_irods_item)
    assert "('value1', 'unit1')" in result
    assert "('value2', 'unit2')" in result


def test_format_delta_time_from_seconds(env):
    template = env.from_string("{{ 3661.5 | format_delta_time }}")
    assert template.render() == "01:01:01.50"


def test_format_delta_time_with_days(env):
    template = env.from_string("{{ delta | format_delta_time }}")
    delta = datetime.timedelta(days=2, hours=3, minutes=4, seconds=5)
    assert template.render(delta=delta) == "2d 03:04:05.00"


def test_format_delta_time_zero_precision(env):
    template = env.from_string("{{ 65 | format_delta_time(sec_precision=0) }}")
    assert template.render() == "00:01:05"


def test_iter_intersection_default(env):
    template = env.from_string("{{ ([1,2,3] | iter_intersection([2,3,4])) | sort }}")
    assert template.render() == "[2, 3]"


def test_iter_intersection_with_tuple(env):
    template = env.from_string("{{ ((1,2,3) | iter_intersection((2,3,4))) | sort }}")
    assert template.render() == "[2, 3]"


def test_iter_intersection_with_dict(env):
    template = env.from_string(
        "{{ {'a': 1, 'b': 2} | iter_intersection({'b': 20, 'c': 30}) }}"
    )
    assert template.render() == "{'b': 2}"


def test_bleach_clean_removes_script(env):
    template = env.from_string("{{ suspect | bleach_clean }}")
    result = template.render(
        suspect="<script>alert('xss')</script><p>safe</p><q>quote</q>"
    )
    assert "<script>" not in result
    assert "<p>safe</p>" in result
    assert "<q>quote</q>" in result


def test_bleach_gemeentetnie(env):
    template = env.from_string("{{ suspect | bleach_clean(tags=['p']) }}")
    result = template.render(
        suspect="<script>alert('xss')</script><p>safe</p><q>quote</q>"
    )
    assert "<script>" not in result
    assert "<p>safe</p>" in result
    assert "<q>quote</q>" not in result  # q is not allowed because not explicitly specified
    # print(f"specify p as allowed {result=}")


def test_bleach_clean_allowed_tags(env):
    template = env.from_string("{{ suspect | bleach_clean }}")
    result = template.render(
        suspect="<script>alert('xss')</script><p>safe</p><q>quote</q>"
    )
    # print(f"allowed tags default {result=}")
    assert "<script>" not in result
    assert "<p>safe</p>" in result
    assert "<q>quote</q>" in result


def test_bleach_clean_non_string(env):
    template = env.from_string("{{ suspect | bleach_clean }}")
    assert template.render(suspect=42) == "42"


def test_regex_match(env):
    template = env.from_string("{{ 'hello world' | regex_match('hello') is not none }}")
    assert template.render() == "True"


def test_regex_match_no_match(env):
    template = env.from_string("{{ 'hello world' | regex_match('world') is none }}")
    assert template.render() == "True"


def test_regex_search(env):
    template = env.from_string(
        "{{ 'hello world' | regex_search('world') is not none }}"
    )
    assert template.render() == "True"


def test_irods_to_sha256_checksum(env):
    # Create a known sha256 checksum
    raw = b"\x00" * 32
    irods_checksum = "sha2:" + base64.b64encode(raw).decode()
    template = env.from_string("{{ checksum | irods_to_sha256_checksum }}")
    assert template.render(checksum=irods_checksum) == "00" * 32


def test_irods_to_sha256_checksum_none(env):
    template = env.from_string("{{ (none | irods_to_sha256_checksum) is none }}")
    assert template.render() == "True"


def test_irods_to_sha256_checksum_invalid_prefix(env):
    template = env.from_string("{{ ('md5:abc' | irods_to_sha256_checksum) is none }}")
    assert template.render() == "True"


def test_os_env(env, monkeypatch):
    monkeypatch.setenv("MANGO_TEST_VAR", "test_value")
    template = env.from_string("{{ 'MANGO_TEST_VAR' | os_env }}")
    assert template.render() == "test_value"


def test_os_env_default(env):
    template = env.from_string("{{ 'NONEXISTENT_VAR_XYZ' | os_env('default_val') }}")
    assert template.render() == "default_val"


def test_b64encode(env):
    template = env.from_string("{{ 'hello' | b64encode }}")
    assert template.render() == "aGVsbG8="


def test_shorten_name_short_string(env):
    template = env.from_string("{{ 'short' | shorten_name }}")
    assert template.render() == "short"


def test_shorten_name_long_string(env):
    template = env.from_string(
        "{{ 'this_is_a_very_long_filename.txt' | shorten_name }}"
    )
    assert template.render() == "this_is...ame.txt"


def test_convert_timestamp_datetime(env):
    ts = 0  # epoch
    template = env.from_string("{{ ts | convert_timestamp_datetime }}")
    result = template.render(ts=ts)
    # Result depends on timezone, but should contain the year 1970
    assert "1970" in result


def test_format_timestamp_default(env):
    ts = datetime.datetime(2024, 1, 15, 12, 30, 45).timestamp()
    template = env.from_string("{{ ts | format_timestamp }}")
    assert template.render(ts=ts) == "2024-01-15 12:30:45"


def test_format_timestamp_iso(env):
    ts = datetime.datetime(2024, 1, 15, 12, 30, 45).timestamp()
    template = env.from_string("{{ ts | format_timestamp('iso-seconds') }}")
    assert template.render(ts=ts) == "2024-01-15T12:30:45"


def test_format_timestamp_custom(env):
    ts = datetime.datetime(2024, 1, 15, 12, 30, 45).timestamp()
    template = env.from_string("{{ ts | format_timestamp('%Y/%m/%d') }}")
    assert template.render(ts=ts) == "2024/01/15"


def test_mango_jinja_utils_apply_template(env):
    utils = MangoJinjaUtils(env)
    result = utils.apply_jinja_template("Hello {{ name }}!", name="World")
    assert result == "Hello World!"


def test_mango_filesizeformat():
    env = Environment(extensions=[MangoJinjaExtension], autoescape=True)
    template = env.from_string("{{ 2048 | mango_filesizeformat | safe }}")
    result = template.render()
    assert result == '<span title="2048 bytes">2.0 kB</span>'


def test_mango_filesizeformat_with_custom_wrap_element():
    env = Environment(extensions=[MangoJinjaExtension], autoescape=True)
    template = env.from_string(
        "{{ 87654321 | mango_filesizeformat(wrap_element='td', binary=True) }}"
    )
    result = template.render()
    assert result == '<td title="87654321 bytes">83.6 MiB</td>'
