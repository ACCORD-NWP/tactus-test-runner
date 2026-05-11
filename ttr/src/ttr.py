"""Tactus-test-runner main driver."""

import argparse
import contextlib
import copy
import glob
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import tomli
from tactus.__main__ import main as tactus_main
from tactus.config_parser import BasicConfig, ConfigPaths, GeneralConstants, ParsedConfig
from tactus.datetime_utils import as_datetime
from tactus.fullpos import flatten_list
from tactus.general_utils import merge_dicts
from tactus.host_actions import TactusHost
from tactus.logs import logger


class TestCases:
    """Class to orchestrate the tests."""

    def __init__(self, args):
        """Construct the object.

        Args:
            args (argsparse objectl): Command line arguments

        """
        ConfigPaths.CONFIG_DATA_SEARCHPATHS.insert(
            0, os.path.join(os.getcwd(), "config_files")
        )

        self.tactus_host = TactusHost().detect_tactus_host()

        definitions = {"general": {}, "modifs": {}}
        if args.config_file is not None:
            logger.info("Using config file: {}", args.config_file)
            self.config = ParsedConfig.from_file(args.config_file, json_schema={})
            try:
                definitions = self.config.expand_macros().dict()
            except KeyError:
                definitions = self.config.dict()

        self.verbose = args.verbose
        self.cases = definitions.get("cases", {})
        try:
            self.reference_date = as_datetime(
                f"{definitions['general']['reference_date']}T00:00:00Z"
            ).date()
        except KeyError:
            self.reference_date = date.today()
        self.cmds = {}
        self.mode = definitions["general"].get("mode", "suite")
        self.extra = definitions["general"].get("extra", [])
        self.get_tag(definitions)
        self.dry = args.dry if args.dry else definitions["general"].get("dry", False)
        self.modifs = definitions["modifs"]
        self.test_dir = definitions.get("test_dir", f"{self.tag}configs")
        self.ial = definitions.get("ial", {})
        self.gl = definitions.get("gl", {})
        self.selection = self.resolve_selection(definitions)

        if args.config_file is not None:
            with contextlib.suppress(KeyError):
                if definitions["ial"].get("active", False):
                    self.update_binary_paths()
        logger.info(" tag: {}", self.tag)
        logger.info(" test_dir: {}", self.test_dir)

    def get_tag(self, definitions):
        """Get and validate tag.

        Arguments:
            definitions (dict) : Configuration

        Raises:
            ValueError: If tag has leading digits

        """
        if "tag" not in definitions["general"]:
            definitions["general"]["tag"] = self.get_tactus_version()
            logger.info("tag not given but derived from git information")
        self.tag = definitions["general"].get("tag")

        if self.tag[0].isdigit():
            raise ValueError(f"The tag cannot start with an integer. tag={self.tag}")

    def resolve_selection(self, definitions):
        """Resolve the selections.

        Arguments:
            definitions (dict) : Configuration

        Returns:
            selection (list) : List of selected configurations
        """
        selection = definitions["general"].get("selection", [])
        if len(selection) == 0:
            logger.info("Selection is empty, include all cases")
            selection = list(self.cases)

        # Handle subtags and update selection accordingly
        with contextlib.suppress(KeyError):
            subtags = definitions["general"]["compiler"]
            subtag_selection = []
            for tag, value in subtags.items():
                if not value.get("active", False):
                    continue
                for sel in selection:
                    if any(x in sel for x in value.get("exclude", "")):
                        continue
                    subtag = f"{tag}{sel}"
                    x = copy.deepcopy(self.cases[sel])
                    if "base" not in x:
                        x["base"] = sel
                    if "host" in x:
                        x["host"] = f"{tag}{x['host']}"
                    x["subtag"] = tag
                    x["extra"] = [] if "extra" not in x else list(x["extra"])
                    for k in value.get("extra", []):
                        x["extra"].append(k)
                    subtag_selection.append(subtag)
                    self.cases[subtag] = x
            if len(subtag_selection) > 0:
                selection = subtag_selection

        return selection

    def list(self):
        """List configurations."""
        logger.info("Available cases:")
        for x in self.cases:
            logger.info("    {}", x)
        logger.info("Selected cases:")
        for x in self.selection:
            logger.info("    {}", x)
            if self.verbose:
                logger.info("      {}", self.cases[x])

    def get_tactus_version(self):
        """Get tactus version info."""
        with open("pyproject.toml", "rb") as f:
            pyproject = tomli.load(f)
            tactus_git = pyproject["tool"]["poetry"]["dependencies"]["tactus"]

        try:
            if "branch" in tactus_git:
                cmd = (
                    f"git ls-remote {tactus_git['git']} refs/heads/{tactus_git['branch']}"
                )
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, check=False
                )
                tag = tactus_git["branch"]
                if result.stderr:
                    logger.error(result.stderr)
                else:
                    hash_ = result.stdout.split("\t")[0][0:7]
                    tag += f"_{hash_}"
            else:
                tag = next(tactus_git[x] for x in ["tag", "rev"] if x in tactus_git)
        except StopIteration:
            tag = "Unknown"
        for character in ["/", ".", "-"]:
            tag = tag.replace(character, "_")
        tag += "_"
        return tag

    def prepare(self):
        """Prepare the host cases.

        Raises:
            KeyError: If case is not found

        Returns:
            host_cases: List of host cases
        """
        try:
            host_cases = [
                self.cases[case]["host"]
                for case in self.selection
                if "host" in self.cases[case]
            ]
        except KeyError as err:
            raise KeyError(
                f"The case is not an available\n"
                f" Avaiable cases are {list(self.cases)}"
            ) from err

        return host_cases

    def create(self, host_cases=None):
        """Create the tests.

        Arguments:
            host_cases (list, optional): List of host cases

        """
        os.makedirs(self.test_dir, exist_ok=True)
        if host_cases is None:
            cases = self.selection
            label = ""
        else:
            label = "host "
            cases = host_cases

        logger.info("Create {}config files in {}", label, self.test_dir)

        assigned = {}
        days_difference = (date.today() - self.reference_date).days
        for i, (case, item) in enumerate(self.cases.items()):
            assigned[case] = i + 1 + days_difference

            if case not in cases or "config_name" in self.cases[case]:
                continue

            counter = assigned[item["host"]] if "host" in item else assigned[case]
            base = item["base"] if "base" in item else case
            subtag = item["subtag"] if "subtag" in item else ""
            host_case = item["hostname"] if "hostname" in item else ""
            host_domain = item["hostdomain"] if "hostdomain" in item else ""
            extra = list(self.extra) + (list(item["extra"]) if "extra" in item else [])

            # Merge and replace macros
            modifs = merge_dicts(self.modifs, self.cases[case].get("modifs", {}), True)
            config = self.config.copy(
                update={
                    "modifs": modifs,
                    "modif_macros": {
                        "counter": counter,
                        "host_case": host_case,
                        "host_domain": host_domain,
                        "tag": self.tag,
                        "subtag": subtag,
                    },
                }
            )
            with contextlib.suppress(KeyError):
                config = config.expand_macros(True)

            # Save the modifications
            outfile = f"{self.test_dir}/modifs_{case}.toml"
            logger.info(" create: {}", outfile)
            BasicConfig.save_dictionary_as(config["modifs"], outfile)

            # Build the command to execute
            cmd = [
                "case",
                f"?{GeneralConstants.PACKAGE_DIRECTORY}/data/config_files/configurations/{base}",
                extra,
                outfile,
                "-o",
                self.test_dir,
            ]
            self.cmds[case] = flatten_list(cmd)

    def configure(self, config_hosts=False, cmds=None):
        """Configure tests.

        Arguments:
            config_hosts (bool, optional): Flag for updating the case settings
                                           with host information
            cmds (list, optional): List of commands (str)

        Returns:
            cases (dict): Dict of cases to run
        """
        if cmds is None:
            cmds = []
        cases = {}
        for case, cmd in self.cmds.items():
            if "config_name" in self.cases[case]:
                continue

            logger.info("Configure case {} with\n", case)
            for c in cmds:
                cmd.append(c)
            cmd_txt = " ".join(cmd)
            logger.info("Use cmd:\n\n{}\n\n", cmd_txt)

            # Call tactus main to create new config, and possibly start suite
            tactus_main(cmd)

            # Update the case settings
            directory = Path(self.test_dir)
            config_file = max(directory.glob("*.toml"), key=lambda f: f.stat().st_mtime)
            with open(config_file, "rb") as f:
                definitions = tomli.load(f)

            self.cases[case]["config_name"] = os.path.basename(config_file.stem)
            self.cases[case]["domain_name"] = definitions["domain"]["name"]

            if config_hosts:
                cases[case] = {
                    "config_name": os.path.basename(config_file.stem),
                    "domain_name": definitions["domain"]["name"],
                }

        return cases

    def get_binaries(self):
        """Get the correct binaries."""
        host_settings = {
            "lumi": {"compiler": "gnu", "precision": "R64"},
            "atos_bologna": {"compiler": "intel", "precision": "R64"},
        }

        basedir = os.getcwd()
        ial_hash = self.ial["ial_hash"]
        build_tar_path = self.ial["build_tar_path"]
        try:
            _bindir = self.modifs["submission"]["task_exceptions"]["Forecast"]["bindir"]
        except KeyError:
            _bindir = (
                f"{self.ial['user_binary_path']}/{ial_hash}/@COMPILER@/@PRECISION@/bin"
            )

        files = glob.glob(f"{build_tar_path}/*{ial_hash}*.tar")
        for f in files:
            ff = os.path.basename(f).replace(".tar", "")
            compiler = host_settings[self.tactus_host]["compiler"]
            precision = host_settings[self.tactus_host]["precision"]
            if "-sp-" in ff:
                precision = "R32"
            if "-gnu-" in ff:
                compiler = "gnu"
            cptag = ff.replace(ial_hash, "").replace("ial", "")
            bindir = (
                _bindir.replace("@CPTAG@", cptag)
                .replace("@IAL_HASH@", ial_hash)
                .replace("@COMPILER@", compiler)
                .replace("@PRECISION@", precision)
                .replace("/bin", "")
            )
            os.makedirs(bindir, exist_ok=True)
            os.chdir(bindir)
            logger.info("Untar {} into {}", f, bindir)
            if not self.dry:
                os.system(f"tar xf {f}")  # noqa S605

        os.chdir(basedir)

        if self.gl:
            gl_hash = self.gl["gl_hash"]
            build_tar_path = self.gl["build_tar_path"]

            try:
                _bindir = self.modifs["submission"]["bindir_gl"]
            except KeyError:
                _bindir = f"{self.gl['user_binary_path']}/{gl_hash}/@COMPILER@/bin"

            files = glob.glob(f"{build_tar_path}/*{gl_hash}*.tar")
            for f in files:
                ff = os.path.basename(f).replace(".tar", "")
                compiler = host_settings[self.tactus_host]["compiler"]
                if "-gnu-" in ff:
                    compiler = "gnu"
                cptag = ff.replace(gl_hash, "").replace("gl", "")
                bindir = (
                    _bindir.replace("@CPTAG@", cptag)
                    .replace("@IAL_HASH@", gl_hash)
                    .replace("@COMPILER@", compiler)
                    .replace("/bin", "")
                )
                os.makedirs(bindir, exist_ok=True)
                os.chdir(bindir)
                logger.info("Untar {} into {}", f, bindir)
                if not self.dry:
                    os.system(f"tar xf {f}")  # noqa S605

        logger.info("All binaries copied. Rerun without '-p' to launch tests")

    def update_binary_paths(self):
        """Update the correct binaries in the internal config object."""
        ial_hash = self.ial.get("ial_hash", "latest")
        prefix = f"hash_{ial_hash[0:7]}_"
        self.tag = prefix

        gl_hash = self.gl.get("gl_hash", "latest")
        bin_modifs = {
            "submission": {
                "bindir": f"{self.ial['user_binary_path']}/{ial_hash}/@COMPILER@/R64/bin",
                "task_exceptions": {
                    "Forecast": {
                        "bindir": (
                            f"{self.ial['user_binary_path']}/{ial_hash}/"
                            "@COMPILER@/@PRECISION@/bin"
                        )
                    }
                },
            }
        }
        if self.gl.get("active", False):
            bin_modifs["submission"][
                "bindir_gl"
            ] = f"{self.gl['user_binary_path']}/{gl_hash}/@COMPILER@/bin"
        self.modifs = merge_dicts(bin_modifs, self.modifs, True)

    def update_hostnames(self, hostnames):
        """Update host and domain name.

        Arguments:
            hostnames (dict): Dict of host cases with properties

        """
        for case, item in self.cases.items():
            if "host" in item and item["host"] in hostnames:
                logger.info(
                    "Add {} and {} to {}",
                    hostnames[item["host"]]["config_name"],
                    hostnames[item["host"]]["domain_name"],
                    case,
                )
                self.cases[case]["hostname"] = hostnames[item["host"]]["config_name"]
                self.cases[case]["hostdomain"] = hostnames[item["host"]]["domain_name"]

    def start(self):
        """Start the run."""
        for case in self.cmds:
            config_name = self.cases[case]["config_name"]
            if self.mode == "task":
                cmds = [
                    [
                        "run",
                        "--config-file",
                        f"{self.test_dir}/{config_name}.toml",
                        "--task",
                        task,
                        "--job",
                        f"{self.test_dir}/{task}.{config_name}.job",
                        "--output",
                        f"{self.test_dir}/{task}.{config_name}.log",
                    ]
                    for task in self.cases[case]["tasks"]
                ]
            else:
                cmds = [
                    [
                        "start",
                        "suite",
                        "--config-file",
                        f"{self.test_dir}/{config_name}.toml",
                        "-f",
                        f"{self.test_dir}/{config_name}.def",
                        "-k",
                    ]
                ]

            for cmd in cmds:
                cmd_txt = " ".join(cmd)
                logger.info("Use cmd:\n\n{}\n\n", cmd_txt)

                # Start suite or task with tactus
                if not self.dry:
                    tactus_main(cmd)


def execute(t, args):
    """Execute the stuff.

    Arguments:
        t (TestCases object): Object with test cases to execute
        args (ArgsPares object): Command line arguments

    """
    # Check dependencies and create possible host cases
    host_cases = t.prepare()
    t.create(host_cases)
    hostnames = t.configure(config_hosts=True)
    t.update_hostnames(hostnames)
    # Create the modification files
    t.create()

    # Run
    if args.run:
        t.configure()
        t.start()


def main(argv=None):
    """Main routine for the test runner."""
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        default=False,
        help="List selected cases",
        required=False,
    )
    parser.add_argument(
        "--remove",
        "-r",
        action="store_true",
        default=False,
        help="Remove cases from ecflow, disks and archive",
        required=False,
    )
    parser.add_argument(
        "--dry",
        "-d",
        action="store_true",
        default=False,
        help="Do not execute the actual action (tactus case, cleaning, ...) only prepare",
        required=False,
    )
    parser.add_argument(
        "--execute-removal",
        action="store_true",
        default=False,
        help="Preform the cleaning. Only works with '--remove' and overrides '--dry'",
        required=False,
    )
    parser.add_argument(
        "--config-file",
        "-c",
        dest="config_file",
        help="Used config file",
        required=False,
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Increase verbosity",
        required=False,
    )
    parser.add_argument(
        "--prepare-binaries",
        "-p",
        action="store_true",
        default=False,
        help="Prepare binaries from an IAL hash",
        required=False,
    )

    parser.add_argument(
        "-m",
        action="store_false",
        dest="run",
        default=True,
        help="Only run the modify generation step",
        required=False,
    )

    parser.add_argument(
        "--config-files-to-remove",
        "-q",
        dest="remove_search_path",
        nargs="*",
        help="Config files for cases to remove",
        required=False,
    )

    args = parser.parse_args(argv)

    t = TestCases(args=args)

    if args.prepare_binaries:
        t.get_binaries()

    elif args.remove:
        if args.remove_search_path is not None:
            files = args.remove_search_path
        elif t.test_dir is not None:
            files = [
                p
                for p in Path(".").glob(f"{t.test_dir}/*.toml")
                if "modifs_" not in p.name
            ]
        else:
            files = []
        args.config_files = files
        args.dry_run = args.dry
        remove_config_file = "config_files/remove.toml"
        with open(remove_config_file, "rb") as f:
            remove_config = tomli.load(f)
        logger.info("Read cleaning rules from {}", remove_config_file)
        args.force_remove = remove_config["remove"].pop("force_remove", False)

    elif args.list:
        t.list()

    elif args.config_file is not None:
        execute(t, args)


if __name__ == "__main__":
    logger.enable(GeneralConstants.PACKAGE_NAME)

    main()
