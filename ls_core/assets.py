from pathlib import Path
import urllib.parse
from ls_core.runtime import APP_DIR, APP_VERSION

def asset_path(relative_path):
    rel=str(relative_path).replace("\\","/").lstrip("/")
    path=(APP_DIR / rel).resolve()
    if APP_DIR.resolve() not in path.parents:
        raise ValueError("Asset path escapes LocalSunoDb root")
    return path

def asset_text(relative_path):
    return asset_path(relative_path).read_text(encoding="utf-8")

def asset_url(relative_path):
    rel=str(relative_path).replace("\\","/").lstrip("/")
    return "/ls-static/" + urllib.parse.quote(rel, safe="/") + "?v=" + urllib.parse.quote(APP_VERSION)

def render_template_tokens(relative_path, values):
    text = asset_text(relative_path)
    for index, value in enumerate(values):
        text = text.replace(f"@@LS{index}@@", str(value))
    return text


def script_asset_boundary(relative_path):
    """Break out of an existing classic-script block and load one versioned JS asset."""
    return '</script><script src="' + asset_url(relative_path) + '"></script><script>'


def stylesheet_asset(relative_path):
    """Return one versioned stylesheet link."""
    return '<link rel="stylesheet" href="' + asset_url(relative_path) + '">'
