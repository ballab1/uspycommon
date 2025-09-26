# DRP Microservice Framework
The microservice framework provides the developer with a common set of libraries. The framework reduces toil by eliminating repetitive tasks, robust error handling, logging, and providing a consistent behavior across all microservices.
# Framework development
This section is intended for people developing the framework package. Usage of the package can be found in the `Developer use of the framework` section.
## Package
* `setup.cfg` contains the package details.
* Create a virtual environment
  * `python3.9 -m venv /path/to/new/virtual/environment`
  * `source <path-to-new-virtual-environment>/bin/activate`
* On the top of repo, install the modules required: `pip3 install -r build/requirements-build.txt`. This will install build, pytest and other modules, necessray for building and unit testing the package.
* Build the package using the command `python3 -m build` at the repo top level. This will produce the package file `dist/drp-package-uspycommon-0.0.3.tar.gz` containing the content under the `src` directory.
* The framework was developed with python version 3.9.
* Install the package by executing the command `pip3 install dist/drp-package-uspycommon-0.0.3.tar.gz`.
* Currently, the version is hard coded to `0.0.3`. During development, the developer may or may not want to change this. So far, changing does not address any extra use case.
* The package will be published to Artifactory under repo `drp-uspytemplate`. . The package build and publishing will be done by Jenkins. Developers must not publish the package directly from their VM to Artifactory.
* `bin/command_ref.txt` lists the commands and explains more.
* In order to publish to and to download from Artifactory, the following `pip.conf` was used.
```
[drp-uspycommon]$ cat /etc/pip.conf
[global]
timeout = 30
download-cache = /home/pip-cache
disable-pip-version-check = True
index-url = http://devpi.prod.k8s.home:3141/testuser/dev/simple/
trusted-host =
    devpi.prod.k8s.home:3141
```
Note: To install the package from Artifactory, execute the command `pip3 install drp-package-uspycommon==<VERSION>`. To see the list of available versions, go tohttp://devpi.prod.k8s.home:3141/testuser/dev/simple/drp-package-uspycommon/. For testing, there is a staging Pypi repo that can be used (http://devpi.prod.k8s.home:3141/testuser/dev/simple/).
## Test
### Unit test
1. On the top of repo, do: `pip3 install -e .`
2. On the top of repo or anywhere under `tests` directory, do: `pytest` (you could also pick specific tests to run)
3. Add/Modify files in src/ or tests/ if necessary for development.
### Integration test
The `int_test.py` file simulates a microservice usage of the framework. While the unit tests consume the content under `src` directly, the `int_test.py` consumes the content which has been installed on the `venv` or `devVm`. Therefore, before running the `int_test.py` to test a package, please build the package and install it.
## Linting
The `.pylintrc` file is located at the top of the repo. Invoke pylint - `pylint --rcfile <.pylintrc location> <filenames>`. One can copy `.pylintrc` in the home directory to avoid the `--rcfile` option.
