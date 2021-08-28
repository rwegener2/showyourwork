from snakemake.utils import min_version


min_version("6.7.0")


report: "report/workflow.rst"


include: "rules/config.smk"
include: "rules/constants.smk"
include: "rules/errors.smk"
include: "rules/repo.smk"
include: "rules/auxfiles.smk"
include: "rules/documentclass.smk"
include: "rules/tree.smk"
include: "rules/meta.smk"
include: "rules/figure.smk"
include: "rules/pdf.smk"
include: "rules/arxiv.smk"
