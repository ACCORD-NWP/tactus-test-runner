"""Clean tactus test cases."""

import os

import tomli
from deode.cleaning import CleanDeode
from deode.config_parser import ParsedConfig
from deode.derived_variables import set_times
from deode.logs import logger
from deode.scheduler import EcflowServer


def remove_ttr_cases(files, dry_run=True):
    """Clean output from test cases.

    Search for config files in test directory.
    For each config we clean the given paths.

    Args:
        files (List): List of config files to clean for
        dry_run (boolean): No cleaning applied

    Returns:
        None
    """
    if len(files) == 0:
        logger.info("No files no cleaning")
        return False

    with open("config_files/cleaning.toml", "rb") as f:
        ttr_cleaning_config = tomli.load(f)
    defaults = ttr_cleaning_config["cleaning"].get("defaults")
    ttr_cleaning_config["cleaning"].pop("defaults")
    rules = list(ttr_cleaning_config["cleaning"].keys())

    suites = []
    for filename in files:
        # Read and update config
        if os.path.isfile(filename):
            config = ParsedConfig.from_file(filename, json_schema={})
            config = config.copy(update=set_times(config))
            config = config.copy(update=ttr_cleaning_config)
            case = config.expand_macros(True).get("general.case")
        else:
            logger.warning("Cannot find {}", filename)
            continue

        for rule in rules:
            choices = config.get(f"cleaning.{rule}").dict()
            if dry_run:
                for choice in choices:
                    choices[choice]["dry_run"] = True
            cleaner = CleanDeode(config, defaults)
            cleaner.prep_cleaning(choices)
            if dry_run:
                logger.info("Would have cleaned {} rule {}", case, rule)
                for task, settings in cleaner.clean_tasks.items():
                    logger.info("{}:{}", task, settings)
            else:
                cleaner.clean()
            suites.append(case)

    if dry_run:
        logger.info("Would have removed suites {}", suites)
    else:
        try:
            EcflowServer(config).remove_suites(suites, check_if_complete=True)
        except (ModuleNotFoundError, UnboundLocalError):
            logger.warning("ecflow or config not found, suites not removed")

    return True
