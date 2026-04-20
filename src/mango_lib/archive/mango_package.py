"""Attempt at isolating the packaging function in a module with everything it needs
to run from local/iRODS to iRODS, with metadata if the source is iRODS,
WITHOUT celery or steps or any of that.
This should be added to the orchestrator before providing the orchestrator to the function.
The only compulsory arguments of the packaging function are
- an iterator of files
- a buffered writer to tar things into
- a base path to compute the relative path
"""

import functools
import io
import json
from pathlib import Path
from typing import Generator, Iterable

from irods.collection import iRODSCollection
from irods.data_object import iRODSDataObject
from mango_mdconverter.md2dict import convert_metadata_to_dict

from mango_lib.archive import mango_tar

MANIFEST_PREFIX = "data"
MANIFEST_NAME = "manifest-sha256.txt"
LAST_GOOD_WRITE = "last-good-write.json"
LOCAL_FOLDER = Path(".")

MANIFEST_PATH = LOCAL_FOLDER / MANIFEST_NAME
LAST_GOOD_WRITE_PATH = LOCAL_FOLDER / LAST_GOOD_WRITE


def tar_prefix(dataset):
    return f"{dataset}/bag/data"


def add_irods_metadata_to_tar(
    orchestrator: mango_tar.TarOrchestrator,
    item: mango_tar.TarInputItem,
    alt_tar: io.BufferedWriter | None = None,
):
    if not isinstance(item, mango_tar.iRODSInputItem):
        return
    metadata = convert_metadata_to_dict(item.item.metadata.items())

    if len(metadata) == 0:
        # skip further processing
        print(f"NO metadata for {item.name}")

        return

    bytes_buff = json.dumps(metadata).encode()
    metadata_base_path = (
        item.item.path
        if isinstance(item.item, iRODSDataObject)
        else str(Path(item.item.path) / item.item.name)
    )
    tar_input_item = mango_tar.BytesInputItem(
        bytes_buff,
        needs_checksum=True,
        path=f"{metadata_base_path}.metadata.json",
        prefix=item.prefix,
        alt_prefix=item.alt_prefix,
        rel_path=item.rel_path,
    )
    mango_tar.record_checksum(orchestrator, tar_input_item)
    mango_tar.add_bytes_item_to_tar(orchestrator.dest_tar, tar_input_item)

    if alt_tar:
        mango_tar.add_bytes_item_to_tar(alt_tar, tar_input_item)


def packaging_orchestrator(
    orchestrator: mango_tar.TarOrchestrator = None,
    manifest_path: Path = MANIFEST_PATH,
    last_good_write_path: Path = LAST_GOOD_WRITE_PATH,
    metadata_tar: io.BufferedWriter | None = None,
):

    if not isinstance(orchestrator, mango_tar.TarOrchestrator):
        orchestrator = mango_tar.TarOrchestrator()  # initializing!

    # CHECKSUMS FOR MANIFEST
    orchestrator.add_callback("delay_point", "checksum-save", mango_tar.record_checksum)
    orchestrator.add_callback("file_end", "checksum-save", mango_tar.record_checksum)

    flush_checksums = functools.partial(
        mango_tar.flush_checksums,
        filename=manifest_path,
        format="bagit",
        name_field="alt_name",
    )
    orchestrator.add_callback(
        "end",
        "end-manifest-bagit",
        flush_checksums,
    )

    # add metadata
    add_metadata_partial = functools.partial(
        add_irods_metadata_to_tar,
        alt_tar=metadata_tar,
    )
    orchestrator.add_callback("file_end", "add_metadata", add_metadata_partial)
    orchestrator.add_callback(
        "collection_item", "add_collection_metadata", add_metadata_partial
    )

    def log_good_write(orchestrator: mango_tar.TarOrchestrator):
        last_good_write = json.dumps(orchestrator.last_good_write)
        with last_good_write_path.open("w") as last_good_write_fp:
            last_good_write_fp.write(last_good_write)

    orchestrator.add_callback("abort", "flush-checksums", flush_checksums)
    orchestrator.add_callback("abort", "last-good-write", log_good_write)

    orchestrator.add_callback("exception", "flush-checksums", flush_checksums)
    orchestrator.add_callback("exception", "last-good-write", log_good_write)


def parse_file_iterator(
    file_iterator: Iterable, rel_path: str, dataset_name: str
) -> Generator[mango_tar.TarInputItem]:
    for file in file_iterator:
        if isinstance(file, mango_tar.TarInputItem):
            yield file
        elif isinstance(file, iRODSDataObject):
            class_name = mango_tar.iRODSInputItem
        elif isinstance(file, Path):
            class_name = mango_tar.FileInputItem
        else:
            raise TypeError(f"File type not supported for: {file}")
        yield class_name(
            file,
            needs_checksum=True,
            rel_path=rel_path,
            prefix=tar_prefix(dataset_name),
            alt_prefix=MANIFEST_PREFIX,
        )


def parse_folder_iterator(
    folder_iterator: Iterable, rel_path: str, dataset_name: str
) -> Generator[mango_tar.iRODSInputItem]:
    # if isinstance(folder_iterator, iRODSTarInputJSONLReader):
    #     return folder_iterator.get_next_object()
    for folder in folder_iterator:
        if not isinstance(folder, iRODSCollection):
            raise TypeError("Item must be an iRODS Collection")
        yield mango_tar.iRODSInputItem(
            folder,
            rel_path=rel_path,
            prefix=tar_prefix(dataset_name),
            alt_prefix=MANIFEST_PREFIX,
        )


def bag_tar(
    orchestrator: mango_tar.TarOrchestrator,
    dataset_name: str,
    manifest_path: Path = MANIFEST_PATH,
    rel_path: str = str(LOCAL_FOLDER),
):
    manifest_tar_input = mango_tar.FileInputItem(
        manifest_path, rel_path=rel_path, prefix=tar_prefix(dataset_name)
    )
    with manifest_path.open("rb") as manifest_fp:
        mango_tar.stream_fp_to_tar(
            manifest_fp,
            input_item=manifest_tar_input,
            tar_dest=orchestrator.dest_tar,
            read_buffer_size=1048576,
            orchestrator=orchestrator,
        )
    bagit_contents = "BagIt version 0.97\nTag-File-Character-Encoding: UTF-8\n".encode()
    tar_input_item = mango_tar.BytesInputItem(
        bagit_contents, needs_checksum=False, path=f"{dataset_name}/bag/bagit.txt"
    )
    mango_tar.add_bytes_item_to_tar(orchestrator.dest_tar, tar_input_item)


def package_dataset(
    file_iterator: Iterable,
    dest_tar_object: iRODSDataObject | Path,
    base_path: str,  # to compute relative paths
    dataset_name: str = "dummy_dataset",
    folder_iterator: Iterable | None = None,
    orchestrator: mango_tar.TarOrchestrator | None = None,
    local_folder: Path = LOCAL_FOLDER,
    manifest_name: str = MANIFEST_NAME,
    add_metadata_tar: bool = False,
    # rocrate_source=None,
):
    manifest_path = local_folder / manifest_name
    with manifest_path.open("w"):
        pass
    last_good_write_path = local_folder / LAST_GOOD_WRITE

    files = parse_file_iterator(file_iterator, base_path, dataset_name)
    collections = parse_folder_iterator(folder_iterator, base_path, dataset_name)

    # metadata tar
    if add_metadata_tar:
        alt_metadata_tar_path = local_folder / f"{dataset_name}_metadata.tar"
        alt_metadata_tar = alt_metadata_tar_path.open("wb")
    else:
        alt_metadata_tar = None

    # set up orchestrator, from scratch if none is provided
    orchestrator = packaging_orchestrator(
        orchestrator, manifest_path, last_good_write_path, alt_metadata_tar
    )

    writing_mode = "w" if isinstance(dest_tar_object, iRODSDataObject) else "wb"
    dest_tar = dest_tar_object.open(writing_mode)
    try:
        mango_tar.create_tar_from_iterators_and_orchestrator(
            object_iterator=files,
            collection_iterator=collections,
            dest_tar=dest_tar,
            orchestrator=orchestrator,
        )
        if alt_metadata_tar is not None:
            alt_metadata_tar.close()

        # add manifest and bagit
        bag_tar(orchestrator, dataset_name, manifest_path, local_folder)
        # if rocrate_source is not None:
        #     add_rocrate(orchestrator, rocrate_source, MANIFEST_NAME) ??
    except Exception as e:
        print(f"Caught error, check last good write at {last_good_write_path}!")
        raise e
    finally:
        dest_tar.close()
        dest_tar_object.truncate(
            orchestrator.last_good_write["tar_file_end"]
        )  # to make sure the file ends well
