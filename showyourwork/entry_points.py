from .constants import *
from .utils import glob
from .cache import restore_cache, update_cache
import subprocess
import shutil
import os
from pathlib import Path
import argparse
import sys
import re


def main():
    # Parse command line args
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--clean", action="store_true")
    parser.add_argument("-C", "--Clean", action="store_true")
    parser.add_argument("-d", "--dag", action="store_true")

    # Internal arguments
    parser.add_argument(
        "--restore-cache", action="store_true", help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--update-cache", action="store_true", help=argparse.SUPPRESS
    )
    args, snakemake_args = parser.parse_known_args(sys.argv[1:])

    # Subprograms
    if args.clean or args.Clean:
        for ext in FIGURE_EXTENSIONS:
            for file in glob(USER / "figures" / f"*.{ext}"):
                os.remove(file)
        for file in [
            USER / "ms.pdf",
            USER / "dag.pdf",
            USER / ".Snakefile",
            USER / ".helpers.smk",
        ]:
            if file.exists():
                os.remove(file)
        if (USER / ".showyourwork").exists():
            shutil.rmtree(USER / ".showyourwork")
        if args.Clean:
            if (USER / ".snakemake").exists():
                shutil.rmtree(USER / ".snakemake")
        return
    elif args.restore_cache:
        restore_cache()
        return
    elif args.update_cache:
        update_cache()
        return
    elif args.dag:
        files = list(
            (ROOT / "workflow").glob("*")
        )  # NOTE: this includes dotfiles
        for file in files:
            shutil.copy(file, USER)
        dag = subprocess.check_output(
            ["snakemake", "--dag", "--snakefile", ".Snakefile"], cwd=USER
        ).decode()
        with open(USER / "dag.dag", "w") as f:
            print(dag, file=f)
        with open(USER / "dag.pdf", "wb") as f:
            f.write(
                subprocess.check_output(
                    ["dot", "-Tpdf", str(USER / "dag.dag")]
                )
            )
        os.remove(USER / "dag.dag")
        for file in files:
            os.remove(USER / Path(file).name)
        return

    # Process Snakemake defaults
    cores_set = False
    conda_set = False
    for i, arg in enumerate(snakemake_args):
        if re.match("^-c([0-9]*?)$", arg):
            cores_set = True
        if arg == "--use-conda":
            conda_set = True
        if (arg == "-s") or (arg == "--snakefile"):
            raise ValueError(
                "Arguments `-s` or `--snakefile` are not allowed."
            )
    if not cores_set:
        snakemake_args.append("-c1")
    if not conda_set:
        snakemake_args.append("--use-conda")
    snakemake_args.extend(["--snakefile", ".Snakefile"])

    # Copy workflow to user directory
    files = list((ROOT / "workflow").glob("*"))  # NOTE: this includes dotfiles
    for file in files:
        shutil.copy(file, USER)

    # Run Snakemake
    subprocess.check_call(["snakemake"] + snakemake_args, cwd=USER)

    # Remove tempfiles
    for file in files:
        os.remove(USER / Path(file).name)
    for file in glob(USER / "tex" / "*latexindent*.tex"):
        os.remove(file)
