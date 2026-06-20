"""mango_lib.jinja provides a custom Jinja2 Extension , template filters and utility functions

Usage examples:

General use:

```python
from jinja2 import Environment
from mango_lib.jinja import MangoExtension

env = Environment(extensions=[MangoExtension])
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

import datetime
from typing import Callable

from jinja2 import Environment
from jinja2.ext import Extension
from irods.meta import iRODSMeta
from irods.data_object import iRODSDataObject
from irods.collection import iRODSCollection


class MangoJinjaExtension(Extension):
    """Custom Jinja2 extension for Mango library."""

    # Class-level registry for filters
    _filters: dict[str, Callable] = {}

    def __init__(self, environment: Environment):
        super().__init__(environment)
        # Register all collected filters with the environment
        for name, func in self._filters.items():
            environment.filters[name] = func

    @classmethod
    def filter(cls, name: str | None = None) -> Callable:
        """Decorator to register a function as a Jinja2 template filter."""

        def decorator(func: Callable) -> Callable:
            filter_name = name or func.__name__
            cls._filters[filter_name] = func
            return func

        return decorator


@MangoJinjaExtension.filter()
def get_one_irods_metadata(
    irods_item: iRODSDataObject | iRODSCollection,
    metadata_name,
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


@MangoJinjaExtension.filter()
def get_irods_metadata(
    irods_item: iRODSDataObject | iRODSCollection,
    metadata_name,
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


@MangoJinjaExtension.filter()
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
