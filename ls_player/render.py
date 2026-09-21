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

def render_suno_audio_player_state_script_assets():
    return script_asset_boundary('ls_player/static/suno_audio_player_state_script_assets.js')


def render_suno_audio_waveform_loader_script_assets():
    return script_asset_boundary('ls_player/static/suno_audio_waveform_loader_script_assets.js')


def render_suno_audio_player_setup_script_assets():
    return script_asset_boundary('ls_player/static/suno_audio_player_setup_script_assets.js')


def render_suno_hosted_player_script_assets():
    return script_asset_boundary('ls_player/static/suno_hosted_player_script_assets.js')


def render_suno_global_player_script_assets():
    return script_asset_boundary('ls_player/static/suno_global_player_script_assets.js')


def render_suno_audio_play_button_script_assets():
    return script_asset_boundary('ls_player/static/suno_audio_play_button_script_assets.js')


def render_suno_audio_compare_button_script_assets():
    return script_asset_boundary('ls_player/static/suno_audio_compare_button_script_assets.js')


def render_suno_audio_player_script():
    """Return the isolated Suno Library audio player JavaScript."""
    return (
        render_suno_audio_player_state_script_assets()
        + render_suno_audio_waveform_loader_script_assets()
        + render_suno_audio_player_setup_script_assets()
        + render_suno_hosted_player_script_assets()
        + render_suno_global_player_script_assets()
        + render_suno_audio_play_button_script_assets()
        + render_suno_audio_compare_button_script_assets()
    )

def render_suno_global_player_style_assets():
    return "<style>\n" + asset_text('ls_player/static/suno_global_player_style_assets.css') + "</style>"


def render_suno_global_player_markup():
    """Return the persistent bottom-player HTML from its physical template."""
    return asset_text("ls_player/templates/global_player.html")

