"""
### iRODS query utilities

"""

from typing import Any, Callable

from irods.session import iRODSSession


def genquery2_select_dict(
    irods_session: iRODSSession,
    select_columns: dict[str, Callable],
    query_string: str,
    generate_select: bool = True,
) -> list[dict[str, Any]] | ValueError:
    """Execute an iRODS genquery2 expression and transform the result set into a list of dictionaries.

    Info:
        A genquery2 result is a list of a list of string values. This variant provides
        both a more workable dict per record and also transforms the string into more logical
        values

    Args:
        irods_session: a valid iRODSSession object
        select_columns: dictionary of column labels as keys and a
            callable that will be called on the value returned from the genquery2
        query_string: the full query_string or a partial expression omitting the `SELECT ...` part
        generate_select: Generate the `SELECT ...` part based on the `select_columns` keys.

    Returns:
        A dict per record returned from the genquery2 result.\
        If the returned record length does not match the `select_columns` length \
        a `ValueError` is raised

    Example:
        ```python
        coolstuff = genquery2_select_dict(irods_session, {"count": int},
            "select count(DATA_ID) where DATA_PATH like '/zone/home%'", generate_select=False)
        ```

    """

    if generate_select:
        query_string = f"SELECT {', '.join(select_columns.keys())} " + query_string
    q_result = irods_session.genquery2(query_string)

    if not q_result:
        return []

    headers = list(select_columns.keys())
    if len(headers) == len(q_result[0]):
        return [
            {
                headers[key]: select_columns[headers[key]](value)
                for key, value in enumerate(record)
            }
            for record in q_result
        ]
    else:
        raise (ValueError("The number of columns returned from the query does not match the number of select_columns provided."))
