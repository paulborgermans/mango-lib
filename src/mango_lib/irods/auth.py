"""Authentication helpers and proxies for connecting to iRODS zones

In multi-tenant environments like the ManGO Portal or ManGO Flow, there may be multiple zones, 
each with their own operator user. 
This module provides a way to get an iRODSSession for the operator of a given zone, 
which can be used to perform privileged tasks.

"""

import importlib
import logging
import os
from collections.abc import Callable
from typing import Optional

from irods.session import iRODSSession


# get_zone_operator_session(zone:str|None = None, client_user:str|None = None) -> iRODSSession

get_zone_operator_session: Optional[Callable[[Optional[str], Optional[str]], iRODSSession]] = None


def simple_get_zone_operator_session(*args, **kwargs):
    """A simple implementation of get_zone_operator_session that uses the current user's credentials."""

    IRODS_ENV = os.getenv(
        "IRODS_ENVIRONMENT_FILE", os.path.expanduser("~/.irods/irods_environment.json")
    )
    client_user = None
    if "client_user" in kwargs:
        client_user = kwargs["client_user"]
    return iRODSSession(irods_env_file=IRODS_ENV, client_user=client_user)


env_var = "GET_ZONE_OPERATOR_SESSION_FUNCTION"
module_name, func_name = os.getenv(env_var, ":").split(":")
if module_name and func_name:
    module = importlib.import_module(module_name)
    get_zone_operator_session = getattr(module, func_name)
else:
    logging.warning(
        f"Failed to import get_zone_operator_session from environment variable "
        f"{env_var}, falling back to simple implementation."
    )
    get_zone_operator_session = simple_get_zone_operator_session
