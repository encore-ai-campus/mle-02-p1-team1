"""Static documentation: never import application modules or environment files."""
project = "매뉴얼 검색 가이드"
language = "ko"
extensions = []
html_theme = "furo"
html_title = "매뉴얼 검색 가이드"
html_copy_source = False
html_show_sourcelink = False
html_static_path = ["_public"]
html_css_files = ["custom.css"]
exclude_patterns = ["_static/**"]
html_theme_options = {"light_css_variables": {"color-brand-primary": "#166766", "color-brand-content": "#166766"}, "dark_css_variables": {"color-brand-primary": "#72d5c6", "color-brand-content": "#72d5c6"}}
