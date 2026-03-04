# Tactus-test-runner

The Tactus-test-runner runs a number of configurations as defined in the used config file. 

We currently have the following config files under the directory config_files

 - atos_bologna.toml : Complete set of tests for atos_bologna
 - lumi[_large].toml : Complete set of tests for lumi for small or large domains
 - ial_pr_[large]_atos_bologna.toml : Test ia IAL pr on the toy/large domain
 - case_definitions.toml : Definition of all test cases 
 - macors.toml : Some macro definitions
 - modifs_[atos_bologna|lumi].toml : Platform dependent config modifications
 - atos_bologna_ial_pr_example.toml : Example for running with a IAL PR

## Prepare

Define the correct tactus version to use in pyproject.toml. This may be a tag, a branch or a local copy.

- remote git dependency: 
```
[tool.poetry.dependencies]
  deode = {git = "git@github.com:uandrae/Deode-Prototype.git", branch = "release/v0.24.0"}
```

- local repository dependency:
```
[tool.poetry.dependencies]
  deode = {path = "/path/to/local/Deode/repo" }
```

After updating the deode dependency make sure to run `poetry update` to let poetry install the correct one

Optionally define the location of your virtual environment in poetry.toml

```
[virtualenvs]
  in-project = false
  path = "some_useful_path"
```

## Install

Install the package and all tactus dependencies with poetry.

```
poetry install
```

```
poetry shell
```

## Check

```
ttr -c config_files/CURRENT_HOST.toml -l
```

where CURRENT_HOST is one of atos_bologna or lumi

## Run
```
ttr -c config_files/CURRENT_HOST.toml
```

This will create a directory according to the tag and create all config files in this directory. For each config a tactus ecflow run will be launched. To only prepare config files without running tactus do:

```
ttr -c config_files/CURRENT_HOST.toml -d 
```

## Clean

After successful runs and assessment the tested cases can be cleaned from disks and ecflow with e.g.
```
ttr -r -q /scratch/$USER/deode/your_test_tag_*/archive/config.toml

```
This will scan all config files and print what would have been cleanead according to the settings in config_files/remove.toml. I.e. you select the cases to remove by adding their config files after `-q`. To execute the actual cleaning type
```
ttr -r -q /scratch/$USER/deode/your_test_tag_*/archive/config.toml --execute-removal
```

Note that due to a bug in ecflow (server version <=5.15.2) configurations with mirror tasks for LAM -> LAM will not be cleaned but will make the server crash. The current, tedious, way to remove those is the following:

- Checkpoint the ecFlow server through ecflow_ui

- Stop the ecFlow server using: 

```
$ ssh $ECF_HOST sudo systemctl stop ecflow-server
```

- Edit the checkpoint file in /home/$USER/ecflow_server/$ECF_HOST.$ECF_PORT.ecf.check and, restart your ecFlow server using:

```
$ ssh $ECF_HOST sudo systemctl start ecflow-server
```

## Operational like testing

Operational like testing is done with the config files [lumi|atos_bologna]_operational.toml. To test the full chain these tests should be done using the development user accounts on atos and lumi respectively. 

## About the config files

The config file has a for main sections: general, case, modifs and ial. Here we explain the usage of each

### General

The general section defines the selection of cases and possible compiler extensions. If tag is not set it's taken from the used tactus branch or tag. In extra we can define extra config files to include.

```
[general]
  tag = "my_label_"
  extra = []
  selection = [
    "cy49t2_alaro",
    "cy49t2_alaro_target",
  ]
```
Leaving out the selection section will run all defined cases. Check with `-l` how it works.
To test different compilers we can add the compiler section. Here we define the section as active, configurations patterns to exclude and possible extra config files.
```
[general.compiler.gnu_]
  active = true
  exclude = ["cy48t2", "cy46h"]
  extra = ["deode/data/config_files/modifications/submission/atos_bologna_gnu.toml"]

```

To rerun the tests with the same dates as those used when testing prior to tagging set the reference date as 
```
[general]
   reference_date  = "YYYY-MM-DD"
```
on atos and 
```
[modifs.general.times]
   end = "YYYY-MM-DDT00:00:00Z"
   start = "YYYY-MM-DDT00:00:00Z"
```
on in `config_files/modifs_lumi.toml` on lumi. Note though that fdb on lumi only stores data for the most recent weeks.

### Case

Here we define the config settings per case.

- base gives the config to start from
- host defines the forcing run for a target run
- extra is extra config files to add for this specific case
- case.X.modifs.Y allows to modify abitrary config settings for this case only

```
[cases.cy49t2_alaro_eps]
  host = "alaro"
  base = "cy49t2_alaro"
  extra = [
    "deode/data/config_files/include/eps/eps_7members.toml",
    "deode/data/config_files/include/eps/alaro.toml",
  ]

[cases.cy49t2_alaro_eps.modifs.eps.general]
  members = "0:3"
```

### Modifs

Here we define global modifications to the default config files. Works the same way as for the config modifications mentioned above.

```
[modifs.archiving.FDB.fdb.fpgrib_files]
  active = false
```

### IAL

This section is for IAL PR testing. Here we define

- active: Switch on or off
- ial_hash: Full hash of the tarball containing the compiled code produced by the github actions. Find if from the github actions, https://github.com/destination-earth-digital-twins/IAL/actions
- build_tar_path: Path to the tarball
- user_binary_path: The target directory for the binaries

We define which tests to do in single and double precision and which compilers are to be tested the same way it's done in the regular case:

```
[ial]
  active = true
  ial_hash = "be0fe3c3429fcbdf4515f5b58a5cf30689cf66f8"
  build_tar_path = "/scratch/deployde330"

[general]
  selection = [
    "cy49t2_alaro",
    "cy49t2_arome",
    "cy49t2_harmonie_arome",
    "cy49t2_harmonie_arome_R64",
    "cy49t2_arome_R64",
  ]

[general.compiler.gnu_]
  active = true
  extra = ["deode/data/config_files/modifications/submission/atos_bologna_gnu.toml"]

[general.compiler.intel_]
  active = true

```

It is also possible to add custom gl tags for testing new gl binaries by adding a `gl` section:

```
[gl]
  active = true
  build_tar_path = "/scratch/deployde330"
  gl_hash = "5d8a7bbe181cb0d560652872ccaff16210e17778"
  user_binary_path = "/scratch/@USER@/gl_binaries"
```

We can check what configurations to expect by
```
$ poetry run ttr -c config_files/ial_pr_atos_bologna.toml -l
2025-12-05 09:06:45 | INFO     | Using config file: config_files/ial_pr_atos_bologna.toml
2025-12-05 09:06:45 | INFO     |  tag: 2951f1a_
2025-12-05 09:06:45 | INFO     | Available cases:
2025-12-05 09:06:45 | INFO     |     cy49t2_alaro_gnu_R64
2025-12-05 09:06:45 | INFO     |     cy49t2_arome_gnu_R64
2025-12-05 09:06:45 | INFO     |     cy49t2_harmonie_arome_gnu_R64
2025-12-05 09:06:45 | INFO     |     cy49t2_arome_gnu_R32
2025-12-05 09:06:45 | INFO     |     cy49t2_harmonie_arome_gnu_R32
2025-12-05 09:06:45 | INFO     |     cy49t2_alaro_intel_R64
2025-12-05 09:06:45 | INFO     |     cy49t2_arome_intel_R64
2025-12-05 09:06:45 | INFO     |     cy49t2_harmonie_arome_intel_R64
2025-12-05 09:06:45 | INFO     |     cy49t2_arome_intel_R32
2025-12-05 09:06:45 | INFO     |     cy49t2_harmonie_arome_intel_R32
2025-12-05 09:06:45 | INFO     | Selected cases:
2025-12-05 09:06:45 | INFO     |     cy49t2_alaro_gnu_R64
2025-12-05 09:06:45 | INFO     |     cy49t2_arome_gnu_R64
2025-12-05 09:06:45 | INFO     |     cy49t2_harmonie_arome_gnu_R64
2025-12-05 09:06:45 | INFO     |     cy49t2_arome_gnu_R32
2025-12-05 09:06:45 | INFO     |     cy49t2_harmonie_arome_gnu_R32
2025-12-05 09:06:45 | INFO     |     cy49t2_alaro_intel_R64
2025-12-05 09:06:45 | INFO     |     cy49t2_arome_intel_R64
2025-12-05 09:06:45 | INFO     |     cy49t2_harmonie_arome_intel_R64
2025-12-05 09:06:45 | INFO     |     cy49t2_arome_intel_R32
2025-12-05 09:06:45 | INFO     |     cy49t2_harmonie_arome_intel_R32
```
First we need to fetch the binaries
```
$ poetry run ttr -c config_files/ial_pr_atos_bologna.toml -p
2025-12-05 09:09:59 | INFO     | Using config file: config_files/ial_pr_atos_bologna.toml
2025-12-05 09:09:59 | INFO     |  tag: 2951f1a\_
2025-12-05 09:09:59 | INFO     | Untar /scratch/deployde330/ial-sp-2951f1a1dc2df82471e857a3331df8bb35050745.tar into /scratch/snh/ial_binaries/2951f1a1dc2df82471e857a3331df8bb35050745/intel/R32
2025-12-05 09:09:59 | INFO     | Untar /scratch/deployde330/ial-gnu-2951f1a1dc2df82471e857a3331df8bb35050745.tar into /scratch/snh/ial_binaries/2951f1a1dc2df82471e857a3331df8bb35050745/gnu/R64
2025-12-05 09:09:59 | INFO     | Untar /scratch/deployde330/ial-sp-gnu-2951f1a1dc2df82471e857a3331df8bb35050745.tar into /scratch/snh/ial_binaries/2951f1a1dc2df82471e857a3331df8bb35050745/gnu/R32
2025-12-05 09:09:59 | INFO     | Untar /scratch/deployde330/ial-2951f1a1dc2df82471e857a3331df8bb35050745.tar into /scratch/snh/ial_binaries/2951f1a1dc2df82471e857a3331df8bb35050745/intel/R64
2025-12-05 09:09:59 | INFO     | All binaries copied. Rerun without '-p' to launch tests
```
Finally we can launch the runs by
```
$ poetry run ttr -c config_files/ial_pr_atos_bologna.toml 
```
Note the corresponding config file `config_files/ial_pr_large_atos_bologna.toml` for large domain tests.

### Use PR binaries for general testing
We can also define the config so that we pick binaries built and run an arbitray set of configurations. See config_files/atos_bologna_ial_pr_example.toml for details.
