# Pytests for mango_tar and mango_package 


## Overview

To run the tests 4 files are required:
* **test_mango_tar_setup.py** : this file creates the input data required to run the tests as well as a "gold standard" manifest that is used to check the contents of the tar. The setup script first sets up the data and the manifest locally. The local data is then uploaded to iRODS. It is also possible to upload a dataset to iRODS and then add random metadata to either a number of data objects or collections. If metadata is added the paths of the data objects or collections that have metadata are stored in "dataobject_metadata.txt" and "collection_metadata.txt" respectively.
* **test_mango_tar_cases.json** : this data structure is used to keep track of the different tests we want to run.
* **test_mango_tar_cases.py** : the cases file contains the code to create the mango_tar and then mango_package. We can feed the tests that we want to run from mango_tar_cases.json into this file and run them for each "case" (or the way the data that we want to test is generated): 
    - create a local tar from local input
    - create a local package from local input 
    - create a tar in iRODS from local input
    - create a package in iRODS from local input
    - create a tar in iRODS from input in iRODS
    - create a package in iRODS from input in iRODS
This means that if you have 6 tests and 6 cases you will run in total 36 tests (6*6).

* **test_mango_tar.py** : this file contains the actual tests. We want to assert the following expectations: 

    1. Is it a tar file? 
    2. What is inside the tar file?
        - Is the file we expect there?
        - Is the file the expected size?
        - Does the file have the expected checksum? 
        - Empty folders should be ignored
        - Is metadata correctly stored
        - Does the package have the expected structure?



## How to setup test data and run tests

If you are running the script from the first time install the necessary dependencies and create a 
virtual environment using uv:

0. 
```
uv sync
```

(from root)

1. Set the path for the input data in iRODS as environment variable

```
export TEST_MANGO_TAR_COLLECTION=/path/to/my/collection
```
(currently testing in /icts/home/public/[...] in quality)

(Make sure that your are authenticated to where you want to create your input data)

2. Setup files for tarring
```
python tests/test_mango_tar_setup.py
```

You can execute this step once, and keep the data for future test runs

3. Run tests
```
pytest -v
```

## How to run (without setup)

If already have all the input data both locally and in irods you can run the tests as follows:

1. Set up the path to the input data in iRODS as environment variable (skip this step if you already did this)

```
export TEST_MANGO_TAR_COLLECTION=/path/to/my/collection
```

2. Run tests
```
pytest -v
```


> [!TIP]
> You can run test cases separately:
>    ```
>    pytest -v -k "local_to_local"
>    pytest -v -k "local_to_irods"
>    pytest -v -k "tar_irods_to_irods"
>    pytest -v -k "package_irods_to_irods"
>
>    ```




## Input data

The input data is generated using test_mango_tar_setup.py. This includes the files to tar and a "gold standard" manifest to compare. 
The folder structure for the test data should be as follows:
```
- test_data
    - test1_local_to_local
        - data
            - file_1.txt
            - ...
        - test1_local_to_local_manifest.txt
    - test_2_local_to_local
        - data
            - file_1.txt
            - ...
        - test2_local_to_local_manifest.txt

```         

