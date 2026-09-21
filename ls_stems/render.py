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

def render_suno_stems_state_controls_script_assets():
    return script_asset_boundary('ls_stems/static/suno_stems_state_controls_script_assets.js')


def render_suno_stems_loader_script_assets():
    return script_asset_boundary('ls_stems/static/suno_stems_loader_script_assets.js')


def render_suno_stems_panel_events_script_assets():
    return script_asset_boundary('ls_stems/static/suno_stems_panel_events_script_assets.js')


def render_suno_stems_transport_script_assets():
    return script_asset_boundary('ls_stems/static/suno_stems_transport_script_assets.js')


def render_suno_stems_player_script():
    """Compose the isolated Suno Library Stems player JavaScript."""
    return (
        render_suno_stems_state_controls_script_assets()
        + render_suno_stems_loader_script_assets()
        + render_suno_stems_panel_events_script_assets()
        + render_suno_stems_transport_script_assets()
    )

def render_suno_page_stems_style_assets():
    return asset_text('ls_stems/static/suno_page_stems_style_assets.css')


