from pytest_cases import parametrize
from mango_lib.archive import mango_tar, mango_package
from irods.session import iRODSSession
from pathlib import Path
import json
import uuid
from irods.helpers import make_session

INPUT_DATA = Path("tests/input_data")
CASES_JSON = Path("tests/test_mango_tar_cases.json")

with open(CASES_JSON) as file:
    cases = json.load(file)
    local_cases = [case for case in cases if "local" in case["input_data_location"]]
    irods_cases = [case for case in cases if "irods" in case["input_data_location"]]


def get_files(session, contract):
    with contract.open() as f:
        for line in f.readlines():
            yield session.data_objects.get(line.strip().decode())


def get_collections(session, contract):
    with contract.open() as f:
        for line in f.readlines():
            yield session.collections.get(line.strip().decode())


@parametrize("case", local_cases, idgen=lambda case: case["name"])
def case_tar_local_to_local(case, tmp_path):
    """Create a local tar with local input data."""

    output_tar = tmp_path / "output_tar.tar"
    input_folder = INPUT_DATA / case["input_data"]
    manifest = INPUT_DATA / case["manifest"]

    file_generator = (
        mango_tar.FileInputItem(
            directory / filename,
        )
        for directory, _, filenames in input_folder.walk()
        for filename in filenames
    )
    orchestrator = mango_tar.TarOrchestrator()

    with output_tar.open("wb") as dest_tar:
        mango_tar.create_tar_from_iterators_and_orchestrator(
            object_iterator=file_generator,
            collection_iterator=[],
            dest_tar=dest_tar,
            orchestrator=orchestrator,
        )

    yield output_tar, manifest


@parametrize("case", local_cases, idgen=lambda case: case["name"])
def case_tar_local_to_irods(case, irods_session):
    """Create a tar in iRODS with local input data"""

    coll = irods_session.collections.create(
        f"/{irods_session.zone}/home/public/{uuid.uuid4()}"
    )
    tarfile = irods_session.data_objects.create(coll.path + "/test_fromlocal.tar")
    input_folder = INPUT_DATA / case["input_data"]
    manifest = INPUT_DATA / case["manifest"]

    file_generator = (
        mango_tar.FileInputItem(
            directory / filename,
        )
        for directory, _, filenames in input_folder.walk()
        for filename in filenames
    )

    orchestrator = mango_tar.TarOrchestrator()

    with tarfile.open("w") as dest_tar:
        mango_tar.create_tar_from_iterators_and_orchestrator(
            object_iterator=file_generator,
            collection_iterator=[],
            dest_tar=dest_tar,
            orchestrator=orchestrator,
        )

    yield tarfile, manifest
    irods_session.collections.remove(coll.path, recursive=True)


@parametrize("case", irods_cases, idgen=lambda case: case["name"])
def case_tar_irods_to_irods(case, irods_session, test_collection):
    """Create a tar in iRODS with input data in iRODS"""

    coll = irods_session.collections.create(
        f"/{irods_session.zone}/home/public/{uuid.uuid4()}"
    )
    tarfile = irods_session.data_objects.create(coll.path + "/test_fromirods.tar")

    input_data = f"{test_collection}/{case['input_data']}"

    input_data_irods = irods_session.collections.get(input_data)
    file_generator = (
        mango_tar.iRODSInputItem(
            data_object,
        )
        for _, _, data_objects in input_data_irods.walk()
        for data_object in data_objects
    )

    orchestrator = mango_tar.TarOrchestrator()

    with tarfile.open("w") as dest_tar:
        mango_tar.create_tar_from_iterators_and_orchestrator(
            object_iterator=file_generator,
            collection_iterator=[],
            dest_tar=dest_tar,
            orchestrator=orchestrator,
        )

    yield tarfile, f"{test_collection}/{case['manifest']}"
    irods_session.collections.remove(coll.path, recursive=True)


@parametrize("case", irods_cases, idgen=lambda case: case["name"])
def case_package_irods_to_irods(case, irods_session, test_collection, tmp_path):
    """Create a packaged dataset in iRODS with input data in iRODS"""

    coll = irods_session.collections.create(
        f"/{irods_session.zone}/home/public/{uuid.uuid4()}"
    )
    package = irods_session.data_objects.create(coll.path + "/package.tar")
    package_path = Path(package.path)
    parent_collection = str(package_path.parent)

    input_data = f"{test_collection}/{case['input_data']}"
    # create_contract_irods(irods_session, input_data, contract)

    contract_data_objects = irods_session.data_objects.get(
            f"{test_collection}/{case["name"]}/list_of_files.txt"
        )

    contract_collections = irods_session.data_objects.get(
            f"{test_collection}/{case["name"]}/list_of_directories.txt"
        )

    if not irods_session.collections.exists(parent_collection):
        irods_session.collections.create(parent_collection)
    restart_output, orchestrator = mango_package.package_dataset(
        file_iterator=get_files(irods_session, contract_data_objects),
        dest_tar_object=package,
        base_path=input_data,
        dataset_name=case["name"],
        folder_iterator=get_collections(irods_session, contract_collections),
        local_folder=tmp_path,
        return_orchestrator=True,
    )


    yield package, f"{test_collection}/{case['manifest']}", case["name"]
    irods_session.collections.remove(coll.path, recursive=True)
