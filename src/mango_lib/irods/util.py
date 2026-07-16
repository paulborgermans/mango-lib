from irods.access import iRODSAccess
from irods.session import iRODSSession


# @todo review this utility module later again
def setup_mango_collection(
    rods_irods_session: iRODSSession, operator_user: str, collection_name: str = "mango"
) -> str:
    mango_collection = f"/{rods_irods_session.zone}/{collection_name}"

    if not rods_irods_session.collections.exists(mango_collection):
        rods_irods_session.collections.create(mango_collection)
    rods_irods_session.acls.set(
        iRODSAccess("own", mango_collection, user_name=operator_user),
        recursive=True,
    )
    return mango_collection


def setup_realm_plugin_collection(
    irods_session: iRODSSession,
    realm: str,  # also group with read access
    plugin_name: str,
    root_collection: str,
    write_access_group: str | None = None,
) -> str:
    storage_path = f"{root_collection}/{realm}/{plugin_name}"

    if not irods_session.collections.exists(storage_path):
        irods_session.collections.create(storage_path, recurse=True)
        irods_session.acls.set(
            iRODSAccess("read", storage_path, user_name=realm),
            recursive=True,
        )
        if write_access_group is not None:
            irods_session.acls.set(
                iRODSAccess("write", storage_path, user_name=write_access_group),
                recursive=True,
            )
        irods_session.acls.set(iRODSAccess("inherit", storage_path))
    return storage_path


def write_yaml_to_data_object(
    path: str, yaml_contents: dict, irods_session: iRODSSession
) -> None | iRODSDataObject:
    """
    Write a YAML file directly to iRODS
    """
    try:
        data_object = irods_session.data_objects.create(path)
        with data_object.open("w") as file:
            yaml_string = yaml.dump(yaml_contents)
            file.write(yaml_string.encode())
        return data_object
    except Exception as e:
        raise ValueError(f"Error writing YAML to data object: {e}")
