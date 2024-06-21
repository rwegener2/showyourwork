import os
import urllib.request
from collections import ChainMap, OrderedDict
from contextlib import contextmanager
from pathlib import Path

import jinja2
import yaml
from packaging import version

from . import __version__, exceptions, git, paths

try:
    from yaml import CDumper as Dumper
    from yaml import CLoader as Loader
except ImportError:
    # If LibYAML not installed
    from yaml import Dumper, Loader

try:
    import snakemake
except ModuleNotFoundError:
    snakemake = None


@contextmanager
def edit_yaml(file):
    """A context used to edit a YAML file in place.

    Args:
        file (str): The full path to the YAML file.
    """
    if Path(file).exists():
        with open(file, "r") as f:
            contents = yaml.load(f, Loader=Loader)
    else:
        contents = {}
    try:
        yield contents
    finally:
        with open(file, "w") as f:
            print(yaml.dump(contents, Dumper=Dumper), file=f)


def render_config(cwd="."):
    """
    Render any jinja templates in ``showyourwork.yml``, combine with
    ``zenodo.yml``, and save the processed config to a temporary YAML file.

    This temporary YAML file is then used as the configfile for the Snakemake
    workflow.

    Args:
        cwd (str, optional): The path to the working directory.

    Returns:
        dict:
            The user config.

    """
    # Render the user's config file to a dict
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(cwd))
    config = env.get_template("showyourwork.yml").render()
    config = yaml.safe_load(config)

    # Merge with the zenodo config file, if present
    if config.get("cache_on_zenodo", True):
        file = Path(cwd) / "zenodo.yml"
        if file.exists():
            with open(file, "r") as f:
                config.update(yaml.safe_load(f.read()))

    # Save to a temporary YAML file
    with open(paths.user().temp / "showyourwork.yml", "w") as f:
        yaml.dump(config, f)

    return config


def get_run_type():
    """Return the type of the current Snakemake run.

    Options are:

    - ``clean``
    - ``build``
    - ``tarball``
    - ``preprocess``
    - ``other``

    Returns:
        str:
            The type of the current run (one of the options listed above).

    """
    return os.getenv("SNAKEMAKE_RUN_TYPE", "other")


def as_dict(x, depth=0, maxdepth=30):
    """
    Replaces nested instances of OrderedDicts with regular dicts in a dictionary.

    This is useful when parsing a config generated from a YAML file with
    inconsistent use of hyphens.

    Args:
        x: A dictionary or dictionary-like mapping generated from reading a
            YAML file.
        depth(int, optional): Default is ``0``.
        maxdepth(int, optional): Default is ``30``.

    """
    if depth == 0 and not x:
        return {}
    elif depth > maxdepth:
        raise exceptions.ConfigError()

    if type(x) is list:
        y = dict(ChainMap(*[dict(xi) for xi in x if type(xi) is OrderedDict]))
        z = [xi for xi in x if type(xi) is not OrderedDict]
        if len(z):
            if y:
                x = [y]
            else:
                x = []
            x.extend(z)
        else:
            x = y
    elif type(x) is OrderedDict:
        x = dict(x)

    if type(x) is dict:
        for key, value in x.items():
            x[key] = as_dict(value, depth + 1)

    return x


def get_upstream_dependencies(file, dependencies, depth=0):
    """
    Collect user-defined dependencies of a file recursively.
    Returns a list of strings.

    """
    if deps := dependencies.get(file, []):
        res = set()
        for dep in deps:
            res |= set([dep])
            res |= get_upstream_dependencies(dep, dependencies, depth + 1)
    else:
        res = set()
    if not depth:
        return list(res)
    else:
        return res


def parse_overleaf():
    """
    Parse Overleaf configuration options and fill in defaults.

    """
    # Get the config
    config = snakemake.workflow.config

    # Make sure `id` is defined
    config["overleaf"]["id"] = config["overleaf"].get("id", None)

    # Set default for `gh_actions_sync`
    config["overleaf"]["gh_actions_sync"] = config["overleaf"].get(
        "gh_actions_sync", True
    )

    # Make sure `push` and `pull` are defined and they are lists
    config["overleaf"]["push"] = config["overleaf"].get("push", [])
    if config["overleaf"]["push"] is None:
        config["overleaf"]["push"] = []
    elif type(config["overleaf"]["push"]) is not list:
        raise exceptions.ConfigError(
            "Error parsing the config. "
            "The `overleaf.push` field must be a list."
        )
    config["overleaf"]["pull"] = config["overleaf"].get("pull", [])
    if config["overleaf"]["pull"] is None:
        config["overleaf"]["pull"] = []
    elif type(config["overleaf"]["pull"]) is not list:
        raise exceptions.ConfigError(
            "Error parsing the config. "
            "The `overleaf.pull` field must be a list."
        )

    # Ensure all files in `push` and `pull` are in the `src/tex` directory
    for file in config["overleaf"]["push"] + config["overleaf"]["pull"]:
        try:
            Path(file).resolve().relative_to(paths.user().tex)
        except ValueError:
            raise exceptions.ConfigError(
                "Error parsing the config. "
                "Files specified in `overleaf.push` and `overleaf.pull` must "
                "be located under the `src/tex` directory."
            )

    # Ensure no overlap between `push` and `pull`.
    # User could in principle provide a directory in one
    # and a file within that directory in the other and that would
    # not trigger this error; we'll just have to let them live
    # dangerously!
    push_files = set(
        [
            str(Path(file).resolve().relative_to(paths.user().tex))
            for file in config["overleaf"]["push"]
        ]
    )
    pull_files = set(
        [
            str(Path(file).resolve().relative_to(paths.user().tex))
            for file in config["overleaf"]["pull"]
        ]
    )
    if len(push_files & pull_files):
        raise exceptions.ConfigError(
            "Error parsing the config. "
            "One more more files are listed in both `overleaf.push` and "
            "`overleaf.pull`, which is not supported."
        )


def parse_config():
    """
    Parse the current config and fill in defaults.


    """
    # Get current config
    config = snakemake.workflow.config

    # During the preprocessing stage, we import user settings,
    # set defaults, and record additional internal settings.
    # These get recorded in a JSON file which is loaded as
    # the main config file in the build stage, so all these
    # settings are available in both stages.
    if Path(snakemake.workflow.workflow.main_snakefile).name == "prep.smk":
        #
        # -- User settings --
        #

        #: Showyourwork version
        config["version"] = config.get("version", None)

        #: Verbosity
        config["verbose"] = config.get("verbose", False)

        #: Manuscript name
        config["ms_name"] = config.get("ms_name", "ms")

        #: Custom script execution rules
        # Note that these are strings with placeholder values like `script`
        # inside curly braces; these get formatted later, in `preprocess.py`
        # Note also that since we execute everything from the root of the
        # repo, matplotlib won't by default use the `matplotlibrc` file in
        # the scripts directory, so we need to pass it as the special env
        # var $MATPLOTLIBRC.
        config["scripts"] = as_dict(config.get("scripts", {}))
        config["scripts"]["py"] = config["scripts"].get(
            "py",
            f"MATPLOTLIBRC={paths.user().scripts} " + "python {script}",
        )

        #: Custom script dependencies
        config["dependencies"] = as_dict(config.get("dependencies", {}))

        #: Zenodo datasets
        config["datasets"] = as_dict(config.get("datasets", {}))

        #: Overleaf
        config["overleaf"] = as_dict(config.get("overleaf", {}))
        parse_overleaf()

        #: Require inputs to all rules to be present on disk for build to pass?
        config["require_inputs"] = config.get("require_inputs", True)

        #: Allow cached rules to run on CI if there's a cache miss?
        config["run_cache_rules_on_ci"] = config.get(
            "run_cache_rules_on_ci", False
        )

        #: Render the article DAG on build
        config["dag"] = as_dict(config.get("dag", {}))
        config["dag"]["render"] = config["dag"].get("render", False)
        config["dag"]["group_by_type"] = config["dag"].get(
            "group_by_type", False
        )
        config["dag"]["engine"] = config["dag"].get("engine", "sfdp")
        defaults = {
            "shape": "box",
            "penwidth": "2",
            "width": "1",
        }
        defaults.update(config["dag"].get("node_attr", {}))
        config["dag"]["node_attr"] = defaults
        defaults = {"ranksep": "1", "nodesep": "0.65"}
        defaults.update(config["dag"].get("graph_attr", {}))
        config["dag"]["graph_attr"] = defaults
        config["dag"]["ignore_files"] = config["dag"].get("ignore_files", [])
        if config["dag"]["ignore_files"] is None:
            config["dag"]["ignore_files"] = []
        elif type(config["dag"]["ignore_files"]) is str:
            config["dag"]["ignore_files"] = [config["dag"]["ignore_files"]]

        #: Tectonic settings
        config["user_args"] = config.get("tectonic_args", [])
        if not (
            isinstance(config["user_args"], list)
            and all(isinstance(elem, str) for elem in config["user_args"])
        ):
            raise exceptions.ConfigError(
                "Error parsing the config. "
                "Setting `tectonic_args` must be a list of strings."
            )
        config["synctex"] = config.get("synctex", True)

        #: Optimize the DAG by removing jobs upstream of cache hits
        config["optimize_caching"] = config.get("optimize_caching", False)

        #: Showyourwork stamp settings
        config["stamp"] = as_dict(config.get("stamp", {}))
        config["stamp"]["enabled"] = config["stamp"].get("enabled", True)
        config["stamp"]["size"] = config["stamp"].get("size", 0.75)
        config["stamp"]["xpos"] = config["stamp"].get("xpos", 1.0)
        config["stamp"]["ypos"] = config["stamp"].get("ypos", 1.0)
        config["stamp"]["angle"] = config["stamp"].get("angle", -20)
        config["stamp"]["url"] = as_dict(config["stamp"].get("url", {}))
        config["stamp"]["url"]["enabled"] = config["stamp"]["url"].get(
            "enabled", False
        )
        config["stamp"]["url"]["maxlen"] = config["stamp"]["url"].get(
            "maxlen", 40
        )

        #: Showyourwork margin_icon settings
        config["margin_icons"] = as_dict(config.get("margin_icons", {}))
        config["margin_icons"]["colors"] = as_dict(
            config["margin_icons"].get("colors", {})
        )
        config["margin_icons"]["monochrome"] = config["margin_icons"].get(
            "monochrome", False
        )
        config["margin_icons"]["colors"]["github"] = config["margin_icons"][
            "colors"
        ].get("github", "0.12,0.47,0.71")
        config["margin_icons"]["colors"]["sandbox"] = config["margin_icons"][
            "colors"
        ].get("sandbox", "0.80,0.14,0.19")
        config["margin_icons"]["colors"]["cache"] = config["margin_icons"][
            "colors"
        ].get("cache", "0.12,0.47,0.71")
        config["margin_icons"]["colors"]["dataset"] = config["margin_icons"][
            "colors"
        ].get("dataset", "0.12,0.47,0.71")

        #
        # -- Internal settings --
        #

        # Cache settings
        config["cache"] = config.get("cache", {})

        # Path to the user repo
        config["user_abspath"] = paths.user().repo.as_posix()

        # Path to the workflow
        config["workflow_abspath"] = paths.showyourwork().workflow.as_posix()

        # TeX auxiliary files
        config["tex_files_in"] = [
            file.as_posix()
            for file in (paths.showyourwork().resources / "tex").glob("*")
        ]

        # The main tex file and the compiled pdf
        config["ms_tex"] = (
            paths.user().tex.relative_to(paths.user().repo)
            / (config["ms_name"] + ".tex")
        ).as_posix()
        config["ms_pdf"] = config["ms_name"] + ".pdf"

        # The parsed config file
        config["config_json"] = (
            (paths.user().temp / "config.json")
            .relative_to(paths.user().repo)
            .as_posix()
        )

        # Paths to the TeX stylesheets
        config["stylesheet"] = "showyourwork.tex"
        config["stylesheet_meta_file"] = "showyourwork-metadata.tex"

        # Script extensions
        config["script_extensions"] = list(config["scripts"].keys())

        # Overridden in the `preprocess` rule
        config["tree"] = {"figures": {}}

        # Overridden in `userrules.py`
        config["cached_deps"] = []

        # Overridden in the `dag` checkpoint
        config["dag_dependencies"] = {}
        config["dag_dependencies_recursive"] = {}

        # Overridden in the `compile` rule
        config["labels"] = {}

    # The following is run in both the preprocessing stage and the main build.
    # If we ran it only during preprocessing, passing different command line
    # flags to `snakemake` on the next build might have no effect if the
    # preprocess workflow is cached & not triggered. The same would be true if
    # the user git-committed or changed branches in between builds.

    # Git info for the repo
    config["git_sha"] = git.get_repo_sha()
    config["git_url"] = git.get_repo_url()
    config["git_slug"] = git.get_repo_slug()
    config["git_branch"] = git.get_repo_branch()
    config["github_actions"] = os.getenv("CI", "false") == "true"
    config["github_runid"] = os.getenv("GITHUB_RUN_ID", "")
    config["git_tag"] = git.get_repo_tag()
    config["cache"][config["git_branch"]] = config["cache"].get(
        config["git_branch"], {}
    )
    config["cache"][config["git_branch"]]["zenodo"] = config["cache"][
        config["git_branch"]
    ].get("zenodo", None)
    config["cache"][config["git_branch"]]["sandbox"] = config["cache"][
        config["git_branch"]
    ].get("sandbox", None)

    # Showyourwork stamp metadata
    if config["stamp"]["url"]["enabled"]:
        stamp_text = (
            config["git_url"].replace("https://", "").replace("http://", "")
        )
        if (
            trim := len(stamp_text.replace("github.com", "X"))
            - config["stamp"]["url"]["maxlen"]
        ) > 0:
            stamp_text = stamp_text[: -(trim + 3)] + "..."
        stamp_text = stamp_text.replace("_", r"{\_}").replace(
            "github.com", r"{\faGithub}"
        )
        config["stamp"]["text"] = stamp_text
    else:
        config["stamp"]["text"] = ""

    if version.parse(__version__).is_devrelease:
        config["stamp"]["version"] = "dev"
    else:
        config["stamp"]["version"] = __version__
