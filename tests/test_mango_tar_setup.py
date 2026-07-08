import hashlib
import os
import random
import string
from pathlib import Path

from irods.column import Criterion
from irods.exception import DataObjectDoesNotExist
from irods.helpers import make_session
from irods.models import Collection, DataObject

INPUT_DATA = Path("tests/input_data")


def setup_test_data_folder():
    """Create folder test_data if not exists."""
    INPUT_DATA.mkdir(parents=True, exist_ok=True)


def setup_test_collection(session, path):
    try:
        session.collections.create(path)
        print(f"created {path}")
    except Exception as e:
        print(f"An error occured while trying to create collection {path}: {e}")


# def cleanup_test_data_folder():
#     """Remove test_data folder if exists."""


# def setup_case_nested_data(folder_name):
#     base_dir = TEST_DIR / folder_name
#     files_dir = base_dir / "files"
#     files_dir.mkdir(parents=True, exist_ok=True)


def create_contract_local(data_dir, base_dir, contract):
    print(f"Creating contract in {base_dir}")
    contract = base_dir / "list_of_files.txt"
    with contract.open("w") as f:
        f.write(
            "\n".join(
                str(directory / filename)
                for directory, _, filenames in Path(data_dir).walk()
                for filename in filenames
            )
        )


def create_manifest_local(directory_to_read, directory_to_write, manifest_name):

    print(f"Creating {manifest_name} locally.")
    with open(directory_to_write / manifest_name, "w") as manifest:
        for root, dirs, files in Path(directory_to_read).walk():
            for file in files:
                filename = root / file
                with open(filename, "rb") as f:
                    checksum = hashlib.sha256(f.read()).hexdigest()
                    size = os.path.getsize(filename)
                    manifest.write(f"{checksum} {size} {filename}\n")


def create_contract_irods(session, input_dir, base_dir):
    collection = session.collections.get(input_dir)
    contract = session.data_objects.create(f"{base_dir}/list_of_files.txt")
    with contract.open("w") as f:
        for _, _, data_objects in collection.walk():
            for data_object in data_objects:
                f.write(data_object.path.encode())
                f.write("\n".encode())


def create_manifest_and_contract_irods(
    session, collection_to_read, collection_to_write, manifest_name
):
    print(f"Creating {manifest_name} in iRODS.")

    coll = session.collections.get(collection_to_read)

    manifest = session.data_objects.open(f"{collection_to_write}/{manifest_name}", "w")
    contract_data_objects = session.data_objects.open(
        f"{collection_to_write}/list_of_files.txt", "w"
    )
    contract_collections = session.data_objects.open(
        f"{collection_to_write}/list_of_directories.txt", "w"
    )

    try:
        contract_collections.write(f"{coll.path}\n".encode())  # add the root folder

        for _, collections, data_objects in coll.walk():
            for data_object in data_objects:
                with data_object.open("r") as f:
                    checksum = hashlib.sha256(f.read()).hexdigest()
                payload = f"{checksum} {data_object.size} {data_object.path}\n"  # TODO: change this to folder/bag/data/
                manifest.write(bytes(payload, "utf-8"))
                contract_data_objects.write(f"{data_object.path}\n".encode())
            for collection in collections:
                contract_collections.write(f"{collection.path}\n".encode())
    finally:
        manifest.close()
        contract_data_objects.close()
        contract_collections.close()


def create_random_file(path: str, size_in_bytes: int):
    """Creates a file with random contents."""

    with open(path, "wb") as f:
        f.write(os.urandom(size_in_bytes))


def setup_case_simple_data(folder_name):
    """Create data and manifest for case simple local to local."""

    print(f"Setting up {folder_name} locally")
    base_dir = INPUT_DATA / folder_name
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    for i in range(10):
        filename = data_dir / f"file_{i}.txt"
        create_random_file(filename, 10)
    create_manifest_local(data_dir, base_dir, "manifest_simple_data.txt")
    create_contract_local(data_dir, base_dir, "list_of_files.txt")


def setup_case_strange_characters_data(folder_name):
    """Create data and manifest for case strange characters local to local."""

    print(f"Setting up {folder_name} locally")
    base_dir = INPUT_DATA / folder_name
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    strange_characters = [
        "@",
        "!",
        "?",
        "*",
        ".",
        "ê",
        "à",
        "í",
        "è",
        " ",
        "\\",
        "é",
        "ù",
        "$",
        "£",
    ]
    for strange_character in strange_characters:
        filename = data_dir / f"file_{strange_character}.txt"
        create_random_file(filename, 10)
    create_manifest_local(data_dir, base_dir, "manifest_strange_characters_data.txt")
    create_contract_local(data_dir, base_dir, "list_of_files.txt")


def make_nested_folders(folder_name, folder, total_levels=10, level=0):
    if folder_name != "data":
        folder = folder / folder_name
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(10):
        filename = folder / f"file_{i}.txt"
        create_random_file(filename, 10)
    if level != total_levels:
        make_nested_folders(f"folder_{level + 1}", folder, total_levels, level + 1)


def setup_case_nested_data(folder_name):
    """Create data and manifest for case nested local to local."""

    print(f"Setting up {folder_name} locally")
    base_dir = INPUT_DATA / folder_name
    data_dir = base_dir / "data"
    make_nested_folders("data", data_dir, total_levels=3, level=0)
    create_manifest_local(data_dir, base_dir, "manifest_nested_data.txt")
    create_contract_local(data_dir, base_dir, "list_of_files.txt")


def setup_case_empty_folder(folder_name):
    """Create data and manifest for case empty folder local to local"""

    print(f"Setting up {folder_name} locally")
    base_dir = INPUT_DATA / folder_name
    data_dir = base_dir / "data"
    empty_dir = data_dir / "empty_dir"
    not_empty_dir = data_dir / "not_empty_dir"
    empty_dir.mkdir(parents=True, exist_ok=True)
    not_empty_dir.mkdir(parents=True, exist_ok=True)
    for i in range(10):
        filename = not_empty_dir / f"file_{i}.txt"
        create_random_file(filename, 10)
    create_manifest_local(data_dir, base_dir, "manifest_empty_folder_data.txt")
    create_contract_local(data_dir, base_dir, "list_of_files.txt")


def upload_directory_to_iRODS(session, source, destination, suffix=""):
    source = Path(source)
    root = f"{destination}/{source.name}{suffix}"
    session.collections.create(root)
    for item in (
        p
        for p in source.rglob("*")
        if not p.name.startswith(("manifest", "list_of_files"))
    ):
        relative = item.relative_to(source)
        irods_path = f"{root}/{relative.as_posix()}"
        if item.is_dir():
            session.collections.create(irods_path)
        else:
            session.data_objects.put(str(item), irods_path)


def setup_case_data_irods(
    session, folder_name: str, test_collection: str, suffix: str = ""
):
    """Upload the local test data from folder_name to test_collection in iRODS. Optional: you can
    have variations by adding a suffix (or instance '_with_metadata')."""

    print(f"Creating {folder_name}{suffix} in iRODS.")
    source = INPUT_DATA / folder_name  # type: ignore
    upload_directory_to_iRODS(session, source, test_collection, suffix=suffix)
    create_manifest_and_contract_irods(
        session,
        f"{test_collection}/{Path(source).name}{suffix}/data",
        f"{test_collection}/{Path(source).name}{suffix}",
        f"manifest_{folder_name}{suffix}.txt",
    )
    # create_contract_irods(
    #     session,
    #     f"{test_collection}/{Path(source).name}{suffix}/data",
    #     f"{test_collection}/{Path(source).name}{suffix}"
    # )


def write_metadata_file(session, collection_path, filename, paths_to_write):
    """Create a file to keep track of the metadata."""

    dataobject_path = (
        f"{collection_path}/{filename}"  # create a file to store the paths
    )
    try:
        obj = session.data_objects.get(dataobject_path)
    except DataObjectDoesNotExist:
        obj = session.data_objects.create(dataobject_path)

    with obj.open("w") as f:
        for path in paths_to_write:
            f.write(bytes(f"{path[1]}\n", "utf-8"))


def get_random_string(length: int):
    """Creates a random string containing lower case characters, upper case characters and digits."""
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def add_random_dataobject_metadata(
    session, collection_path, manifest_name, number_of_objects=1
):
    """Adds random dataobject metadata to a number of objects in the collection."""

    data = collection_path + "/data"
    print(f"Adding dataobject metadata to {collection_path}")
    query = session.query(Collection.name, DataObject.name).filter(
        Criterion("like", Collection.name, data + "%")
    )

    paths = [
        (
            f"{result[Collection.name]}/{result[DataObject.name]}",
            f"{result[Collection.name].replace(collection_path + '/data', '')}/{result[DataObject.name]}",
        )
        for result in query
    ]

    paths_to_add_metadata = []
    paths_to_add_metadata.extend(
        random.sample(paths, min(number_of_objects, len(paths)))
    )
    for path in paths_to_add_metadata:
        obj = session.data_objects.get(path[0])
        name = get_random_string(10)
        value = get_random_string(10)
        obj.metadata.add(name, value)

    # manifest = session.data_objects.get(collection_path + "/" + manifest_name)
    # with manifest.open("a+") as m:
    #     for path in paths_to_add_metadata:
    #         m.write(f"checksum_placeholder 0 {path}.metadata.json".encode())
    #         m.write("\n".encode())

    write_metadata_file(
        session, collection_path, "dataobject_metadata.txt", paths_to_add_metadata
    )


def add_random_collection_metadata(
    session, collection_path, manifest_name, number_of_objects=1
):
    """Adds random collection metadata to a number of objects in the collection."""

    data = collection_path + "/data"
    query = session.query(Collection.name).filter(
        Criterion(
            "like", Collection.name, data + "/%"
        )  # so neighbours which are a substring are not touched
    )

    paths = [
        (
            f"{result[Collection.name]}",
            f"{result[Collection.name].replace(collection_path + '/data', '')}",
        )
        for result in query
    ]
    if len(paths) == 0:
        print("No collections found to add metadata...")
    else:
        print(f"Adding collection metadata to {collection_path}")
        paths.append(
            (f"{collection_path}/data", "/data")
        )  # adding the root collection as well
        paths_to_add_metadata = paths[:number_of_objects]
        for path in paths_to_add_metadata:
            coll = session.collections.get(path[0])
            name = get_random_string(10)
            value = get_random_string(10)
            coll.metadata.add(name, value)
        write_metadata_file(
            session, collection_path, "collection_metadata.txt", paths_to_add_metadata
        )


if __name__ == "__main__":  # so it does not run each time we run pytest
    setup_test_data_folder()
    setup_case_simple_data("simple_data")
    setup_case_strange_characters_data("strange_characters_data")
    setup_case_nested_data("nested_data")
    setup_case_empty_folder("empty_folder_data")
    with make_session(
        env_file=os.path.expanduser("~/.irods/irods_environment.json"), ssl_settings={}
    ) as session:
        try:
            test_collection = os.environ["TEST_MANGO_TAR_COLLECTION"]
        except KeyError:
            raise Exception(
                "In order to create setup data in iRODS, please set the environment variable TEST_MANGO_TAR_COLLECTION to the path you want to create the data."
            )
        setup_test_collection(session, test_collection)
        setup_case_data_irods(session, "simple_data", test_collection)
        setup_case_data_irods(session, "strange_characters_data", test_collection)
        setup_case_data_irods(session, "nested_data", test_collection)
        setup_case_data_irods(session, "empty_folder_data", test_collection)

        setup_case_data_irods(
            session, "simple_data", test_collection, suffix="_with_metadata"
        )
        add_random_dataobject_metadata(
            session,
            f"{test_collection}/simple_data_with_metadata",
            "manifest_simple_data_with_metadata.txt",
            number_of_objects=2,
        )
        add_random_collection_metadata(
            session,
            f"{test_collection}/simple_data_with_metadata",
            "manifest_simple_data_with_metadata.txt",
            number_of_objects=107,
        )
        setup_case_data_irods(
            session,
            "nested_data",
            test_collection,
            suffix="_with_metadata",  # type: ignore
        )
        add_random_dataobject_metadata(
            session,
            f"{test_collection}/nested_data_with_metadata",
            "manifest_nested_data_with_metadata.txt",
            number_of_objects=5,
        )
        add_random_collection_metadata(
            session,
            f"{test_collection}/nested_data_with_metadata",
            "manifest_nested_data_with_metadata.txt",
            number_of_objects=107,
        )
        setup_case_data_irods(
            session,
            "empty_folder_data",
            test_collection,
            suffix="_with_metadata",  # type: ignore
        )
        add_random_collection_metadata(
            session,
            f"{test_collection}/empty_folder_data_with_metadata",
            "empty_folder_data_with_metadata.txt",
            number_of_objects=2,
        )

        # add metadata on the data (root) folder?
        # add tests -> for nested metadata
        # test for empty collection with metadata
        # add tests for folders with no permissions
        #
