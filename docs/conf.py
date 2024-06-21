# -- Add in cwd to absolute path --------------------------------------------
# This is necessary because sphinx does not know about the $PYTHONPATH
# unless the dev has explicitly created in in their local environment. 
# We'll add it in just to be safe for general doc builds
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import hacks

# -- Project information -----------------------------------------------------

project = "showyourwork"
copyright = "2022, Rodrigo Luger"

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinxcontrib.programoutput",
    "sphinx.ext.napoleon",
]
templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
master_doc = "index"
rst_epilog = """
.. |showyourwork| raw:: html

    <span style="color:red; font-weight:bold; font-style:italic;">showyourwork!</span>
"""

# -- Options for HTML output -------------------------------------------------

html_theme = "sphinx_book_theme"
html_copy_source = True
html_show_sourcelink = True
html_sourcelink_suffix = ""
html_title = "showyourwork"
html_logo = "_static/logo.png"
html_static_path = ["_static"]
html_css_files = ["css/custom.css"]
html_theme_options = {
    "repository_url": "https://github.com/showyourwork/showyourwork",
    "repository_branch": "main",
    "use_edit_page_button": True,
    "use_issues_button": True,
    "use_repository_button": True,
    "use_download_button": True,
    "logo_only": True,
    "use_fullscreen_button": False,
    "path_to_docs": "docs/",
}

# -- Extension settings ------------------------------------------------------

# autodoc
autoclass_content = "both"
autosummary_generate = True
autodoc_docstring_signature = True
autodoc_default_options = {"members": True}
