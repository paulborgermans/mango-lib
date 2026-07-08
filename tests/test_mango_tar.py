import hashlib
import os
import tarfile

import pytest
from irods.session import iRODSSession
from pytest_cases import fixture, parametrize_with_cases

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_MANGO_TAR_COLLECTION"),
    reason="TEST_MANGO_TAR_COLLECTION environment variable is not set"
)


@fixture(scope="module")
def irods_session():
    env_file = os.getenv(
        "IRODS_ENVIRONMENT_FILE", os.path.expanduser("~/.irods/irods_environment.json")
    )
    session = iRODSSession(irods_env_file=env_file)
    # assert session.zone == ZONE --> to be uncommented to avoid testing in wrong zone
    yield session
    session.cleanup()


@fixture(scope="module")
def test_collection():
    yield os.environ["TEST_MANGO_TAR_COLLECTION"]


def get_local_manifest_lines(manifest):
    with open(manifest) as m:
        for line in m.readlines():
            yield line.strip().split(" ", 2)


def get_irods_manifest_lines(irods_session, manifest):
    """Gets checksum, size and path from manifest"""
    with irods_session.data_objects.get(manifest).open("r") as m:
        for line in m.readlines():
            yield line.decode().strip().split(" ", 2)


def get_metadata_lines(irods_session, metadata_file_path):
    """Opens and reads the document that contains the paths of collections or data objects with metadata"""
    with irods_session.data_objects.get(metadata_file_path).open("r") as f:
        for line in f.readlines():
            yield line.decode().strip


def calculate_sha256sum(file_object):
    "Calculate a sha256 checksum of a file object"
    h = hashlib.sha256()
    for chunk in iter(lambda: file_object.read(65536), b""):
        h.update(chunk)
    return h.hexdigest()


@parametrize_with_cases("path_to_tar,manifest", glob="*tar_local_to_local")
def test_local_tar(path_to_tar, manifest):
    assert tarfile.is_tarfile(path_to_tar)
    with tarfile.open(path_to_tar) as tar:
        tarred_files = tar.getnames()
        for checksum_in_manifest, size, file in get_local_manifest_lines(manifest):
            assert file in tarred_files
            member = tar.getmember(file)
            assert member.size == int(size)
            with tar.extractfile(member) as f:
                checksum_in_tar = calculate_sha256sum(f)
            assert checksum_in_manifest == checksum_in_tar


@parametrize_with_cases("path_to_tar,manifest", glob="*tar_local_to_irods")
def test_irods_tar(path_to_tar, manifest):
    with path_to_tar.open("r") as fp:
        assert tarfile.is_tarfile(fp)
        with tarfile.open(fileobj=fp) as tar:
            tarred_files = tar.getnames()
            for checksum_in_manifest, size, file in get_local_manifest_lines(manifest):
                assert file in tarred_files
                member = tar.getmember(file)
                assert member.size == int(size)
                with tar.extractfile(member) as f:
                    checksum_in_tar = calculate_sha256sum(f)
                assert checksum_in_manifest == checksum_in_tar


@parametrize_with_cases(
    "path_to_tar,manifest", glob="*tar_irods_to_irods"
)  # TODO: merge test functions?
def test_irods_to_irods_tar(irods_session, path_to_tar, manifest):
    with path_to_tar.open("r") as fp:
        assert tarfile.is_tarfile(fp)
        with tarfile.open(fileobj=fp) as tar:
            tarred_files = tar.getnames()
            for line in get_irods_manifest_lines(irods_session, manifest):
                checksum_in_manifest, size, file = [item.strip() for item in line]
                assert file in tarred_files
                member = tar.getmember(file)
                assert member.size == int(size)
                with tar.extractfile(member) as f:
                    checksum_in_tar = calculate_sha256sum(f)
                assert checksum_in_manifest == checksum_in_tar


@parametrize_with_cases(
    "path_to_tar,manifest,folder_name", glob="*package_irods_to_irods"
)
def test_irods_to_irods_package(
    irods_session, path_to_tar, manifest, folder_name, test_collection
):
    with path_to_tar.open("r") as fp:
        assert tarfile.is_tarfile(fp)
        with tarfile.open(fileobj=fp) as tar:
            tarred_files = tar.getnames()
            assert f"{folder_name}/bag/bagit.txt" in tarred_files
            assert f"{folder_name}/bag/manifest-sha256.txt" in tarred_files
            for line in get_irods_manifest_lines(irods_session, manifest):
                checksum_in_manifest, size, file = [item.strip() for item in line]
                packaged_file = file.replace(
                    f"{test_collection}/{folder_name}/data", f"{folder_name}/bag/data"
                )  # TODO: set up the manifest so that we don't have to change the path (it should be folder/bag/data/ from the start)
                assert packaged_file in tarred_files
                member = tar.getmember(packaged_file)
                assert member.size == int(size)
                with tar.extractfile(member) as f:
                    checksum_in_tar = calculate_sha256sum(f)
                assert checksum_in_manifest == checksum_in_tar
        fp.seek(0)
        metadata_objects_path = (
            f"{test_collection}/{folder_name}/dataobject_metadata.txt"
        )
        metadata_collections_path = (
            f"{test_collection}/{folder_name}/collection_metadata.txt"
        )

        if irods_session.collections.exists(metadata_objects_path):
            for line in get_metadata_lines(irods_session, metadata_objects_path):
                assert f"{folder_name}/bag/data{line}.metadata.json" in tarred_files
        fp.seek(0)
        if irods_session.collections.exists(metadata_collections_path):
            for line in get_metadata_lines(irods_session, metadata_collections_path):
                if line == "/data":  # if there is metadata on the root collection
                    collection_json = ".metadata.json"
                else:
                    collection_json = f"/{line.split('/')[-1]}.metadata.json"
                assert f"{folder_name}/bag/data{line}{collection_json}" in tarred_files

        # loop trough metadata_objects and check if file.metadata.json is in the tar!

        #     for line in manifest_lines:
        #         checksum_in_manifest, size, file = [item.strip() for item in line]
        #         assert file in tarred_files
        #         member = tar.getmember(file)
        #         assert member.size == int(size)
        #         with tar.extractfile(member) as f:
        #             checksum_in_tar = calculate_sha256sum(f)
        #         assert checksum_in_manifest == checksum_in_tar
