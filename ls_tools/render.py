import base64
import difflib
import hashlib
import importlib.util
import socket
import threading
import html
import json
import os
import shutil
import mimetypes
import re
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import unicodedata
import warnings
import webbrowser
import zipfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath

from ls_core.runtime import *
from ls_core.assets import asset_text, script_asset_boundary

def render_suno_compare_review_script_assets():
    return script_asset_boundary('ls_tools/static/suno_compare_review_script_assets.js')


def render_suno_compare_player_script_assets():
    return script_asset_boundary('ls_tools/static/suno_compare_player_script_assets.js')


def render_suno_compare_item_script_assets():
    return script_asset_boundary('ls_tools/static/suno_compare_item_script_assets.js')


def render_suno_compare_layout_script_assets():
    return script_asset_boundary('ls_tools/static/suno_compare_layout_script_assets.js')


def render_suno_compare_this_script():
    """Render the isolated Compare This inline player and review JavaScript."""
    return (
        render_suno_compare_review_script_assets() +
        render_suno_compare_player_script_assets() +
        render_suno_compare_item_script_assets() +
        render_suno_compare_layout_script_assets()
    )

def render_suno_edit_audio_controls_script_assets():
    return script_asset_boundary('ls_tools/static/suno_edit_audio_controls_script_assets.js')


def render_suno_row_menu_category_helpers_script_assets():
    return script_asset_boundary('ls_tools/static/suno_row_menu_category_helpers_script_assets.js')


def render_suno_row_action_dispatch_script_assets():
    return script_asset_boundary('ls_tools/static/suno_row_action_dispatch_script_assets.js')


def render_suno_row_clipboard_visibility_script_assets():
    return script_asset_boundary('ls_tools/static/suno_row_clipboard_visibility_script_assets.js')


def render_suno_edit_row_actions_script():
    """Render Edit buttons, row menus and track action JavaScript."""
    return (
        render_suno_edit_audio_controls_script_assets() +
        render_suno_row_menu_category_helpers_script_assets() +
        render_suno_row_action_dispatch_script_assets() +
        render_suno_row_clipboard_visibility_script_assets()
    )

def render_suno_launcher_tools_script():
    return script_asset_boundary('ls_tools/static/suno_launcher_tools_script.js')


def render_suno_inline_style_editor_script():
    return (
        script_asset_boundary('ls_tools/static/suno_inline_style_editor_script.js')
        + render_suno_launcher_tools_script()
    )


def render_suno_page_row_actions_menu_style_assets():
    return asset_text('ls_tools/static/suno_page_row_actions_menu_style_assets.css')


def render_suno_page_compare_this_style_assets():
    return asset_text('ls_tools/static/suno_page_compare_this_style_assets.css')


