"""Sphinx configuration for the SQL Mapper API documentation."""

from pathlib import Path
import sys


# Import car_search_rag and group_project.common for autodoc.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

project = "SQL Mapper"
language = "ko"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
]

napoleon_google_docstring = True
napoleon_numpy_docstring = False
autodoc_member_order = "bysource"
autodoc_default_options = {"undoc-members": True}
autodoc_class_signature = "mixed"
autodoc_typehints = "none"
python_maximum_signature_line_length = 70
add_module_names = False
toc_object_entries_show_parents = "hide"
nitpick_ignore_regex = [("py:class", r"^(?!group_project\.).+")]

html_theme = "furo"
html_title = "SQL Mapper Documentation"
html_copy_source = False
html_show_sourcelink = False
html_static_path = ["_static"]
html_css_files = ["custom.css"]
