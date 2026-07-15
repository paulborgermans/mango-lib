"""mango_lib.jinja provides a custom Jinja2 Extension , template filters and utility functions

Usage examples:

General use:

```python
from jinja2 import Environment
from mango_lib.jinja import MangoJinjaExtension

env = Environment(extensions=[MangoJinjaExtension])
template = env.from_string("{{ 3661.5 | format_delta_time }}")
print(template.render())  # 01:01:01.50
```

Use in a Flask app like ManGO portal:

```python
from flask import Flask
from mango_lib.jinja import MangoJinjaExtension

app = Flask(__name__)

# Register the extension with Flask's Jinja environment
app.jinja_env.add_extension(MangoJinjaExtension)
...
```

"""

import base64
import binascii
import datetime
import json
import os
import re
import zoneinfo
from typing import Callable, Iterable

import nh3  # for html and js escape untrusted content
from irods.collection import iRODSCollection
from irods.data_object import iRODSDataObject
from irods.meta import iRODSMeta
from jinja2 import Environment
from jinja2.ext import Extension
from jinja2.filters import do_filesizeformat
from markupsafe import Markup


class MangoJinjaExtension(Extension):
    """Jinja2 extension mainly providing custom filters."""

    # Class-level registry for filters
    _filters: dict[str, Callable] = {}

    def __init__(self, environment: Environment):
        super().__init__(environment)
        # Register all collected filters with the environment
        for name, func in self._filters.items():
            environment.filters[name] = func

    @classmethod
    def template_filter(cls, name: str | None = None) -> Callable:
        """Decorator to register a function as a Jinja2 template filter."""

        def decorator(func: Callable) -> Callable:
            filter_name = name or func.__name__
            cls._filters[filter_name] = func
            return func

        return decorator


class MangoJinjaUtils:
    """Utility class for Mango Jinja stuff.

    Needs the Jinja environment to be passed in the constructor

    """

    def __init__(self, jinja_env: Environment):
        self.jinja_env = jinja_env

    def apply_jinja_template(self, dest_template: str, **variables):
        """Apply a Jinja template to a string with the given variables.

        Typical use case is in automations like ManGO Flow and ingest scripts
        """
        return self.jinja_env.from_string(dest_template).render(**variables)


@MangoJinjaExtension.template_filter()
def get_one_irods_metadata(
    irods_item: iRODSDataObject | iRODSCollection,
    metadata_name: str,
    default_value=None,
    as_tuple=False,
):
    try:
        avu: iRODSMeta = irods_item.metadata.get_one(metadata_name)
        if as_tuple and avu:
            return (avu.value, avu.units)
        return avu.value if avu else default_value
    except Exception:
        return default_value  # iRODSMeta(metadata_name, default_value)


@MangoJinjaExtension.template_filter()
def get_irods_metadata(
    irods_item: iRODSDataObject | iRODSCollection,
    metadata_name: str,
    default_value=[],
    as_tuple=False,
) -> list:
    try:
        avu: list[iRODSMeta] = irods_item.metadata.get_all(metadata_name)
        if avu and as_tuple:
            return [(a.value, a.units) for a in avu]
        return [a.value for a in avu] if avu else default_value
    except Exception:
        return default_value  # iRODSMeta(metadata_name, default_value)


@MangoJinjaExtension.template_filter()
def format_delta_time(
    delta: float | int | datetime.timedelta,
    sec_precision: int = 2,
    variant: str = "compact",
) -> str:
    """jinja2 template filter to format a timedelta or seconds as a human-readable string."""
    if isinstance(delta, (float, int)):
        delta = datetime.timedelta(seconds=delta)

    if sec_precision not in range(0, 7):
        sec_precision = 2

    # timedelta gives days, seconds, and microseconds
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    sub_second = delta.microseconds // 10 ** (6 - sec_precision)

    if variant == "compact":
        # Format with a day prefix
        return (
            f"{f'{days}d ' if days else ''}{hours:02}:{minutes:02}:{seconds:02}"
            f"{f'.{sub_second:0{sec_precision}}' if sec_precision > 0 else ''}"
        )

    return ""


@MangoJinjaExtension.template_filter()
def iter_intersection(set1: Iterable, set2: Iterable, return_type: str | type = "auto"):
    if return_type == "auto":
        return_type = type(set1) if isinstance(set1, (set, list, tuple, dict)) else set
    if return_type is list:
        return list(set(set1).intersection(set(set2)))
    elif return_type is tuple:
        return tuple(set(set1).intersection(set(set2)))
    elif return_type is dict:
        return {k: v for k, v in set1.items() if k in set2}
    else:
        return return_type(set1).intersection(set(set2))  # type: ignore


@MangoJinjaExtension.template_filter()
def intersection(set1, set2):
    return iter_intersection(set1, set2, return_type=set)


@MangoJinjaExtension.template_filter()
def bleach_clean(suspect: str, **kwargs) -> str:
    """Escapes dangerous content for html and js

    The name bleach_clean is for BC when it was using
    the now unsupported bleach library. `nh3` is rust based and much faster too"""
    if "tags" in kwargs:
        kwargs["tags"] = set(kwargs["tags"])
    if type(suspect) is str:
        return nh3.clean(suspect, **kwargs)
    else:
        return suspect


@MangoJinjaExtension.template_filter()
def regex_match(_string: str, _re: str) -> re.Match | None:
    return re.match(_re, _string)


@MangoJinjaExtension.template_filter()
def regex_search(_string: str, _re: str) -> re.Match | None:
    return re.search(_re, _string)


@MangoJinjaExtension.template_filter()
def irods_to_sha256_checksum(irods_checksum: str | None) -> str | None:
    if irods_checksum is None or not irods_checksum.startswith("sha2:"):
        return None
    return binascii.hexlify(base64.b64decode(irods_checksum[5:])).decode("utf-8")


@MangoJinjaExtension.template_filter()
def os_env(parameter: str, default=None) -> str | None:
    return os.environ.get(parameter, default)


@MangoJinjaExtension.template_filter()
def b64encode(string: str) -> str:
    return base64.b64encode(string.encode("utf-8")).decode()


@MangoJinjaExtension.template_filter()
def shorten_name(
    string: str, max_length: int = 25, prefix_length: int = 7, suffix_length: int = 7
) -> str:
    if len(string) < max_length:
        return string
    return f"{string[:prefix_length]}...{string[-suffix_length:]}"


@MangoJinjaExtension.template_filter()
def convert_timestamp_datetime(ts: int | float) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(ts)


@MangoJinjaExtension.template_filter()
def format_timestamp(ts: int | float, format: str = "%Y-%m-%d %H:%M:%S") -> str:
    if format.lower() == "iso":
        return datetime.datetime.fromtimestamp(ts).isoformat()
    elif format.lower() == "iso-seconds":
        return datetime.datetime.fromtimestamp(ts).isoformat(timespec="seconds")
    elif format.lower() == "iso-milliseconds":
        return datetime.datetime.fromtimestamp(ts).isoformat(timespec="milliseconds")
    return datetime.datetime.fromtimestamp(ts).strftime(format)


@MangoJinjaExtension.template_filter()
def format_datetime(
    value: datetime.datetime,
    format="%Y-%m-%d %H:%M:%S",
    local_timezone="Europe/Brussels",
):

    return value.astimezone(zoneinfo.ZoneInfo(local_timezone)).strftime(format)


@MangoJinjaExtension.template_filter()
def mango_filesizeformat(value, binary=False, wrap_element="span"):
    """Custom filesizeformat filter that returns a span
    with a title attribute for the full size in bytes."""
    return Markup(
        f'<{wrap_element} title="{value} bytes">{do_filesizeformat(value, binary=binary)}</{wrap_element}>'
    )

@MangoJinjaExtension.template_filter()
def pprint_as_json(anything, indent=2):
    return json.dumps(anything, indent=indent)