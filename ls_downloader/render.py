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
from ls_core.assets import asset_text, asset_url, render_template_tokens, script_asset_boundary, stylesheet_asset

def render_downloader_section_navigation_script():
    return script_asset_boundary('ls_downloader/static/downloader_section_navigation_script.js')


def render_downloader_wav_workflow_script():
    return script_asset_boundary('ls_downloader/static/downloader_wav_workflow_script.js')


def render_downloader_elza_layout_script():
    return script_asset_boundary('ls_downloader/static/downloader_elza_layout_script.js')


def render_downloader_settings_modal_script():
    """Legacy page slot retained until the Downloader shell is renamed."""
    return ""


def render_downloader_action_status_script():
    return script_asset_boundary('ls_downloader/static/downloader_action_status_script.js')


def render_downloader_working_status_script():
    return script_asset_boundary('ls_downloader/static/downloader_working_status_script.js')


def render_downloader_metadata_job_script_assets():
    return script_asset_boundary('ls_downloader/static/downloader_metadata_job_script_assets.js')


def render_downloader_metadata_audit_script():
    """Return only the current metadata backfill job JavaScript."""
    return render_downloader_metadata_job_script_assets()

def render_downloader_token_bridge_script():
    return script_asset_boundary('ls_downloader/static/downloader_token_bridge_script.js')


def render_downloader_state_script():
    return script_asset_boundary('ls_downloader/static/downloader_state_script.js')


def render_downloader_restored_selection_script_assets():
    return script_asset_boundary('ls_downloader/static/downloader_restored_selection_script_assets.js')


def render_downloader_restored_metadata_actions_script_assets():
    return script_asset_boundary('ls_downloader/static/downloader_restored_metadata_actions_script_assets.js')


def render_downloader_ignored_import_script_assets():
    return script_asset_boundary('ls_downloader/static/downloader_ignored_import_script_assets.js')


def render_downloader_restored_terminal_script_assets():
    return script_asset_boundary('ls_downloader/static/downloader_restored_terminal_script_assets.js')


def render_downloader_restored_view_script():
    """Return restored Downloader result actions and event delegation JavaScript."""
    return "".join((
        render_downloader_restored_selection_script_assets(),
        render_downloader_restored_metadata_actions_script_assets(),
        render_downloader_ignored_import_script_assets(),
        render_downloader_restored_terminal_script_assets(),
    ))

def render_downloader_update_workflows_script():
    return script_asset_boundary('ls_downloader/static/downloader_update_workflows_script.js')


def render_downloader_shell_style_assets():
    return asset_text('ls_downloader/static/downloader_shell_style_assets.css')


def render_downloader_cards_metadata_style_assets():
    return asset_text('ls_downloader/static/downloader_cards_metadata_style_assets.css')


def render_downloader_panel_controls_style_assets():
    return asset_text('ls_downloader/static/downloader_panel_controls_style_assets.css')


def render_downloader_tracklist_tools_style_assets():
    return asset_text('ls_downloader/static/downloader_tracklist_tools_style_assets.css')


def render_downloader_status_preview_style_assets():
    return asset_text('ls_downloader/static/downloader_status_preview_style_assets.css')


def render_downloader_page_styles():
    """Return versioned Downloader stylesheets in the original cascade order."""
    return "".join((
        stylesheet_asset('ls_downloader/static/downloader_shell_style_assets.css'),
        stylesheet_asset('ls_downloader/static/downloader_cards_metadata_style_assets.css'),
        stylesheet_asset('ls_downloader/static/downloader_panel_controls_style_assets.css'),
        stylesheet_asset('ls_downloader/static/downloader_tracklist_tools_style_assets.css'),
        stylesheet_asset('ls_downloader/static/downloader_status_preview_style_assets.css'),
    ))

def render_downloader_status_markup():
    """Return the Downloader working and tip overlays."""
    return asset_text('ls_downloader/templates/status_markup.html')

def render_downloader_connection_section(
    token_invalid_at,
    token,
    token_status,
    masked_token,
    token_updated_at,
    token_source,
    bridge_status,
):
    """Return the simplified Downloader connection zone and its diagnostics."""
    bridge_active = bool(bridge_status.get("bridge_active"))
    if token_invalid_at:
        connection_level = "warn"
        connection_title = "Jāatjauno Suno pieslēgums"
        connection_note = "Atver Suno Create un ļauj Token Bridge saņemt jaunu sesiju."
    elif token and bridge_active:
        connection_level = "ok"
        connection_title = "Suno savienojums ir gatavs"
        connection_note = "Imports var izmantot pašreizējo Suno sesiju."
    elif token:
        connection_level = "warn"
        connection_title = "Tokens saglabāts — tilts nav atrasts"
        connection_note = "WAV un metadatu darbības var strādāt, bet, ja pieslēguma atjaunošana neizdodas, pārbaudi Token Bridge diagnostiku."
    else:
        connection_level = "warn"
        connection_title = "Suno savienojums nav gatavs"
        connection_note = "Pirms WAV vai metadatu darbībām atjauno Suno pieslēgumu."

    token_status_class = "warn" if token_invalid_at or not token else "ok"
    token_mask_html = (
        '<br><span class="muted">' + esc(masked_token) + '</span>'
        if masked_token else ""
    )
    token_update_html = (
        '<br><span class="muted">Atjaunots: ' + esc(token_updated_at)
        + ' · Avots: ' + esc(token_source) + '</span>'
        if token_updated_at else ""
    )
    bridge_level = esc(bridge_status.get("diagnosis_level") or "warn")
    bridge_state = "aktīvs" if bridge_active else "vēl nav atrasts"
    bridge_summary_by_code = {
        "session_expired": "Suno noraidīja saglabāto autorizāciju.",
        "extension_offline": "Token Bridge paplašinājums nav savienots ar LS.",
        "page_not_reporting": "Paplašinājums ir savienots, bet nav saņemta aktuāla Suno lapas diagnostika.",
        "page_bridge_missing": "Suno lapas tilts nepabeidza ielādi.",
        "fetch_hook_inactive": "Suno aizvietoja fetch pārtvērēju; gaida automātisku atjaunošanu.",
        "waiting_for_api_request": "Lapas tilts ir gatavs, bet Suno API pieprasījums vēl nav redzēts.",
        "authorization_missing": "Suno API pieprasījums tika redzēts bez Authorization galvenes.",
        "relay_pending": "Autorizācija ir atrasta, bet LS vēl nav saņēmis tokenu.",
        "healthy": "Visas Token Bridge pārbaudes ir izturētas.",
    }
    bridge_summary = esc(
        bridge_summary_by_code.get(str(bridge_status.get("diagnosis_code") or ""))
        or bridge_status.get("diagnosis_summary")
        or "Gaida diagnostiku…"
    )

    return render_template_tokens('ls_downloader/templates/connection_section.html', [esc(connection_level), esc(connection_title), esc(connection_note), token_status_class, esc(token_status), token_mask_html, token_update_html, bridge_level, bridge_state, bridge_summary])

def render_downloader_metadata_section():
    """Return the Downloader metadata column."""
    return asset_text('ls_downloader/templates/metadata_section.html')

def render_downloader_audio_section():
    """Return the Downloader WAV picker, Local family confirmation, and result zone."""
    local_family_title = get_local_family_title()
    local_family_value = (
        esc(local_family_title)
        if local_family_title
        else "Nav iestatīta — tiks piedāvāts izvēlētās dziesmas nosaukums"
    )

    return render_template_tokens('ls_downloader/templates/audio_section.html', [local_family_value])

def render_downloader_side_panels_markup():
    """Return the Downloader Elza dock markup."""
    return asset_text('ls_downloader/templates/side_panels.html')


