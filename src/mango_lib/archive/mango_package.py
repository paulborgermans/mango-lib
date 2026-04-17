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
from irods.data_object import iRODSDataObject
from irods.collection import iRODSCollection
from mango_mdconverter.md2dict import convert_metadata_to_dict
from pathlib import Path
from typing import Iterable, Generator

from mango_lib.archive import mango_tar

MANIFEST_PREFIX = "data"
LAST_GOOD_WRITE = "last-good-write.json"


def tar_prefix(dataset):
    return f"{dataset}/bag/data"


def packaging_orchestrator(
    orchestrator: mango_tar.TarOrchestrator = None,
    manifest_name: str = "manifest-sha256.txt",
    last_good_write_name: str = "last_good_write.json",
):

    if not isinstance(orchestrator, mango_tar.TarOrchestrator):
        orchestrator = mango_tar.TarOrchestrator()  # initializing!
    orchestrator.add_callback("file_end", "checksum-save", mango_tar.record_checksum)
    flush_checksums = functools.partial(
        mango_tar.flush_checksums,
        filename=manifest_name,
        format="bagit",
        name_field="alt_name",
    )
    orchestrator.add_callback(
        "end",
        "end-manifest-bagit",
        flush_checksums,
    )

    # ADD METADATA CALLBACK
    def exit_gracefully(orchestrator: mango_tar.TarOrchestrator):
        last_good_write = json.dumps(orchestrator.last_good_write)
        with Path(last_good_write_name).open("w") as last_good_write_fp:
            last_good_write_fp.write(last_good_write)

    orchestrator.add_callback("exception", "flush-checksums", flush_checksums)
    orchestrator.add_callback("exception", "last-good-write", exit_gracefully)


def parse_file_iterator(
    file_iterator: Iterable, rel_path: str, dataset_name: str
) -> Generator[mango_tar.TarInputItem]:
    # if isinstance(file_iterator, iRODSTarInputJSONLReader):
    #     return file_iterator.get_next_object()
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
    folder_iterator: Iterable, rel_path: str = ".", dataset_name: str = ""
) -> Generator[mango_tar.iRODSInputItem]:
    # if isinstance(folder_iterator, iRODSTarInputJSONLReader):
    #     return folder_iterator.get_next_object()
    for folder in folder_iterator:
        if not isinstance(folder, iRODSCollection):
            raise TypeError("Item must be an iRODS Collection")
        yield mango_tar.iRODSInputItem(
            folder, rel_path=rel_path, prefix=tar_prefix(dataset_name)
        )


def bag_tar(
    dest_tar: iRODSDataObject | io.BufferedWriter,
    orchestrator: mango_tar.TarOrchestrator,
    dataset_name: str,
    manifest_path: Path = Path("manifest-sha256.txt"),
    rel_path: str = ".",
):
    manifest_tar_input = mango_tar.FileInputItem(
        manifest_path, rel_path=rel_path, prefix=tar_prefix(dataset_name)
    )
    with manifest_path.open("rb") as manifest_fp:
        mango_tar.stream_fp_to_tar(
            manifest_fp,
            input_item=manifest_tar_input,
            tar_dest=dest_tar,
            read_buffer_size=1048576,
            orchestrator=orchestrator,
        )


def add_irods_metadata_to_tar(
    orchestrator: mango_tar.TarOrchestrator,
    item: mango_tar.TarInputItem,
    rel_path="",
    prefix: str = "",
    alt_prefix: str = "",
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
    tar_input_item = mango_tar.BytesInputItem(
        (
            f"{item.item.path}.metadata.json"  # type: ignore
            if isinstance(item.item, iRODSDataObject)
            else f"{item.item.path}/{item.item.name}.metadata.json"
        ),
        bytes_buff,
        needs_checksum=True,
        prefix=prefix,
        alt_prefix=alt_prefix,
        rel_path=rel_path,
    )
    mango_tar.record_checksum(orchestrator, tar_input_item)
    mango_tar.add_bytes_item_to_tar(orchestrator.dest_tar, tar_input_item)
    if alt_tar:
        mango_tar.add_bytes_item_to_tar(alt_tar, tar_input_item)


def package_dataset(
    file_iterator: Iterable,
    dest_tar: iRODSDataObject | io.BufferedWriter,
    base_path: str,
    orchestrator: mango_tar.TarOrchestrator | None = None,
    folder_iterator: Iterable | None = None,
    dataset_name: str = "dummy_dataset",
    manifest_path: Path = Path("manifest-sha256.txt"),
    local_folder: Path = Path("."),
    # rocrate_source=None,
):
    with manifest_path.open("w"):
        pass
    last_good_write_path = local_folder / LAST_GOOD_WRITE
    files = parse_file_iterator(file_iterator, base_path, dataset_name)
    collections = parse_folder_iterator(folder_iterator, base_path, dataset_name)
    orchestrator = packaging_orchestrator(
        orchestrator, str(manifest_path), str(last_good_write_path)
    )

    # add metadata
    alt_metadata_tar_path = local_folder / f"{dataset_name}_metadata.tar"
    alt_metadata_tar = alt_metadata_tar_path.open("wb")
    add_metadata_partial = functools.partial(
        add_irods_metadata_to_tar,  # from frigo.py
        dest_tar=dest_tar,
        prefix=tar_prefix(dataset_name),
        alt_prefix=MANIFEST_PREFIX,
        rel_path=base_path,
        alt_tar=alt_metadata_tar,
    )
    orchestrator.add_callback("file_end", "add_metadata", add_metadata_partial)
    orchestrator.add_callback(
        "collection_item", "add_collection_metadata", add_metadata_partial
    )

    # the meat
    try:
        mango_tar.create_tar_from_iterators_and_orchestrator(
            object_iterator=files,
            collection_iterator=collections,
            dest_tar=dest_tar,
            orchestrator=orchestrator,
        )
        alt_metadata_tar.close()
        bag_tar(dest_tar, orchestrator, dataset_name, manifest_path, local_folder)
        # if rocrate_source is not None:
        #     add_rocrate(dest_tar, rocrate_source, MANIFEST_NAME)
    except Exception as e:
        print(f"Caught error, check last good write at {last_good_write_path}!")
        raise e
    finally:
        dest_tar.close()
