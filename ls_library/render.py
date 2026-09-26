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
from ls_core.assets import asset_text, asset_url, render_template_tokens, script_asset_boundary
from ls_data.repository import get_track_local_family_titles

def build_local_playback_url(track_id, has_confirmed_local_audio):
    if not has_confirmed_local_audio:
        return ""
    value = str(track_id or "").strip()
    if not value:
        return ""
    return "/local-audio?track_id=" + urllib.parse.quote(value)


def render_suno_panel_layout_script():
    return script_asset_boundary('ls_library/static/suno_panel_layout_script.js')


def render_suno_right_dock_order_script():
    return script_asset_boundary('ls_library/static/suno_right_dock_order_script.js')


def render_suno_flags_tags_dock_script():
    return script_asset_boundary('ls_library/static/suno_flags_tags_dock_script.js')


def render_selected_track_panel_script():
    return script_asset_boundary('ls_library/static/selected_track_panel_script.js')


def render_track_text_editor_script():
    return script_asset_boundary('ls_library/static/track_text_editor_script.js')


def render_style_modal_close_script():
    return script_asset_boundary('ls_library/static/style_modal_close_script.js')


def render_suno_rating_tags_script():
    return script_asset_boundary('ls_library/static/suno_rating_tags_script.js')


def render_suno_saved_views_tag_state_script(user_tags_initial_json, pinned_user_tags_initial_json):
    """Bootstrap tag state, then load the physically separated Library JS."""
    try:
        user_tags = json.loads(user_tags_initial_json or "[]")
    except Exception:
        user_tags = []
    try:
        pinned_tags = json.loads(pinned_user_tags_initial_json or "[]")
    except Exception:
        pinned_tags = []
    payload = json.dumps({"userTags": user_tags, "pinnedUserTags": pinned_tags}, ensure_ascii=False).replace("</", "<\\/")
    return (
        "window.LS_LIBRARY_BOOTSTRAP = Object.assign(window.LS_LIBRARY_BOOTSTRAP || {}, " + payload + ");\n"
        + script_asset_boundary("ls_library/static/suno_saved_views_tag_state.js")
    )


def render_suno_tag_editor_script_assets():
    return script_asset_boundary('ls_library/static/suno_tag_editor_script_assets.js')


def render_suno_tag_filter_script_assets():
    return script_asset_boundary('ls_library/static/suno_tag_filter_script_assets.js')


def render_suno_saved_views_script_assets():
    return script_asset_boundary('ls_library/static/suno_saved_views_script_assets.js')


def render_suno_saved_views_tag_filters_script(
    user_tags_initial_json,
    pinned_user_tags_initial_json,
):
    """Return Saved Views and tag-filter UI JavaScript for Suno Library."""
    return (
        render_suno_saved_views_tag_state_script(
            user_tags_initial_json,
            pinned_user_tags_initial_json,
        )
        + render_suno_right_dock_order_script()
        + render_suno_flags_tags_dock_script()
        + render_suno_tag_editor_script_assets()
        + render_suno_tag_filter_script_assets()
        + render_suno_saved_views_script_assets()
    )

def render_suno_filter_navigation_script():
    return script_asset_boundary('ls_library/static/suno_filter_navigation_script.js')


def render_suno_navigation_work_status_script():
    return script_asset_boundary('ls_library/static/suno_navigation_work_status_script.js')


def render_suno_working_overlay_script():
    return script_asset_boundary('ls_library/static/suno_working_overlay_script.js')


def render_suno_wav_local_family_script():
    return script_asset_boundary('ls_library/static/suno_wav_local_family_script.js')


def render_suno_working_overlay_lifecycle_script():
    return script_asset_boundary('ls_library/static/suno_working_overlay_lifecycle_script.js')


def render_suno_autoplay_rows_script(sort_column_js, sort_direction_js):
    """Bootstrap row/sort state, then load the physically separated Library JS."""
    try:
        sort_column = json.loads(str(sort_column_js or "null"))
    except Exception:
        sort_column = None
    payload = json.dumps({
        "sortColumn": sort_column,
        "sortDirection": str(sort_direction_js or "asc"),
    }, ensure_ascii=False).replace("</", "<\\/")
    return (
        "window.LS_LIBRARY_BOOTSTRAP = Object.assign(window.LS_LIBRARY_BOOTSTRAP || {}, " + payload + ");\n"
        + script_asset_boundary("ls_library/static/suno_autoplay_rows.js")
    )


def render_suno_selection_state_script():
    return script_asset_boundary('ls_library/static/suno_selection_state_script.js')


def render_suno_selection_checkbox_script():
    return script_asset_boundary('ls_library/static/suno_selection_checkbox_script.js')


def render_suno_keyboard_navigation_script():
    return script_asset_boundary('ls_library/static/suno_keyboard_navigation_script.js')


def render_suno_selection_actions_script():
    return script_asset_boundary('ls_library/static/suno_selection_actions_script.js')


def render_suno_view_state_sort_script():
    return script_asset_boundary('ls_library/static/suno_view_state_sort_script.js')


def render_suno_menu_search_core_script_assets():
    return script_asset_boundary('ls_library/static/suno_menu_search_core_script_assets.js')


def render_suno_sidebar_stats_search_events_script_assets():
    return script_asset_boundary('ls_library/static/suno_sidebar_stats_search_events_script_assets.js')


def render_suno_menu_help_settings_shell_script_assets():
    return script_asset_boundary('ls_library/static/suno_menu_help_settings_shell_script_assets.js')


def render_suno_settings_actions_script_assets():
    return script_asset_boundary('ls_library/static/suno_settings_actions_script_assets.js')


def render_suno_menus_search_settings_script():
    """Render Suno Library top menus, Finder search, help, stats and settings JavaScript."""
    return (
        render_suno_menu_search_core_script_assets() +
        render_suno_sidebar_stats_search_events_script_assets() +
        render_suno_menu_help_settings_shell_script_assets() +
        render_suno_settings_actions_script_assets()
    )

def render_suno_user_tag_catalog_actions_script():
    return script_asset_boundary('ls_library/static/suno_user_tag_catalog_actions_script.js')


def render_suno_sort_indicator_script():
    return script_asset_boundary('ls_library/static/suno_sort_indicator_script.js')


def render_suno_selection_restore_open_url_script():
    return script_asset_boundary('ls_library/static/suno_selection_restore_open_url_script.js')


def render_suno_imported_rows_restore_script():
    return script_asset_boundary('ls_library/static/suno_imported_rows_restore_script.js')

def render_suno_library_lazy_loader_script():
    return script_asset_boundary('ls_library/static/suno_library_lazy_loader.js')


def render_active_filter_bar_html(
    filter_chips,
    saved_views,
    total_rows,
    limit_value,
    sort_by,
    sort_dir,
):
    """Render the active-filter bar, saved views and Reset All control."""
    visible_filter_chips = filter_chips[:5]
    overflow_filter_chips = filter_chips[5:]
    overflow_html = ""
    if overflow_filter_chips:
        overflow_html = f"""
            <details class="ls-filter-overflow">
                <summary aria-label="Show {len(overflow_filter_chips)} more filters">+{len(overflow_filter_chips)}</summary>
                <div class="ls-filter-overflow-menu">
                    {''.join(overflow_filter_chips)}
                </div>
            </details>
        """

    clear_all_params = {}
    if sort_by:
        clear_all_params["sort_by"] = sort_by
        clear_all_params["sort_dir"] = sort_dir
    clear_all_query = urllib.parse.urlencode(clear_all_params)
    clear_all_href = f"/?{clear_all_query}" if clear_all_query else "/"

    if saved_views:
        saved_view_rows = []
        for item in saved_views:
            view_id = str(item.get("id") or "")
            view_name = str(item.get("name") or "")
            view_query = str(item.get("query") or "")
            view_href = f"/?{view_query}" if view_query else "/"
            saved_view_rows.append(f"""
                <div class="ls-saved-view-row" data-saved-view-id="{esc(view_id)}">
                    <a class="ls-saved-view-link" href="{esc(view_href)}" title="Open {esc(view_name)}">{esc(view_name)}</a>
                    <button type="button" class="ls-saved-view-rename" data-saved-view-id="{esc(view_id)}" data-saved-view-name="{esc(view_name)}" title="Rename saved view">Rename</button>
                    <button type="button" class="ls-saved-view-delete" data-saved-view-id="{esc(view_id)}" data-saved-view-name="{esc(view_name)}" title="Delete saved view" aria-label="Delete {esc(view_name)}">×</button>
                </div>
            """)
        saved_views_list_html = "".join(saved_view_rows)
    else:
        saved_views_list_html = '<div class="ls-saved-view-empty">No saved views yet</div>'

    saved_views_control_html = f"""
        <details class="ls-saved-views" id="ls-saved-views">
            <summary title="Open saved views">Views{f' ({len(saved_views)})' if saved_views else ''}</summary>
            <div class="ls-saved-views-menu">
                {saved_views_list_html}
            </div>
        </details>
        <button type="button" class="ls-save-view-button" id="ls-save-view-button">Save view</button>
    """

    if filter_chips:
        chip_group_html = "".join(visible_filter_chips) + overflow_html
        clear_all_html = (
            f'<a class="ls-filter-clear-all" href="{esc(clear_all_href)}" '
            f'title="Reset All filters" aria-label="Reset All filters">'
            f'<svg class="ls-filter-action-icon" viewBox="0 0 20 20" '
            f'aria-hidden="true" focusable="false">'
            f'<path d="M5 5L15 15M15 5L5 15"></path>'
            f'</svg></a>'
        )
        state_label = f"Active filters: {len(filter_chips)}"
    else:
        chip_group_html = '<span class="ls-filter-empty">All tracks</span>'
        clear_all_html = ""
        state_label = "No active filters"

    active_search_html = f"""
        <section class="ls-active-filter-bar" aria-label="{esc(state_label)}">
            <div class="ls-active-filter-main">
                <span class="ls-active-filter-title">Active</span>
                <div class="ls-active-filter-chips">
                    {chip_group_html}
                </div>
            </div>
            <div class="ls-active-filter-meta">
                {saved_views_control_html}
                <span class="ls-filter-result-count" id="ls-filter-result-count" data-state="loading" aria-live="polite">… tracks</span>
            </div>
        </section>
    """
    return active_search_html, clear_all_html

def render_show_more_html(
    *,
    rows_count,
    total_rows,
    limit_value,
    query,
    style_query,
    selected_workspaces,
    workspace_mode,
    selected_categories,
    category_mode,
    selected_local_families,
    kind_filter,
    local_audio_filter,
    search_name,
    search_lyrics,
    search_prompt,
    search_marks,
    search_tags,
    flag_filter_value,
    tag_filter_value,
    selected_track_ids_value,
    sort_by,
    sort_dir,
):
    """Render legacy Show more navigation or the lazy-load sentinel."""
    if total_rows is None:
        return (
            '<div id="library-lazy-sentinel" class="show-more-box" '
            'data-state="idle" aria-live="polite">'
            '<span class="show-more-info">Ielādē dziesmas…</span>'
            '</div>'
        )

    # Search and filters are applied to the complete DB result before LIMIT.
    # Show more only increases that LIMIT while preserving the current view.
    if limit_value != "all" and rows_count < total_rows:
        try:
            current_count = int(limit_value)
        except ValueError:
            current_count = 300
        next_count = min(current_count + current_count, total_rows)
        more_params = {
            "q": query,
            "style_q": style_query,
            "workspace": selected_workspaces,
            "workspace_mode": workspace_mode if workspace_mode == "family_and" else "",
            "category_filter": selected_categories,
            "category_mode": category_mode if category_mode == "family_and" else "",
            "local_family_filter": selected_local_families,
            "kind_filter": kind_filter,
            "local_audio_filter": local_audio_filter,
            "rows": str(next_count),
            "search_name": "1" if search_name else "0",
            "search_lyrics": "1" if search_lyrics else "0",
            "search_prompt": "1" if search_prompt else "0",
            "search_marks": "1" if search_marks else "0",
            "search_tags": "1" if search_tags else "0",
            "flag_filter": flag_filter_value,
            "tag_filter": tag_filter_value,
            "track_ids": selected_track_ids_value,
            "sort_by": sort_by,
            "sort_dir": sort_dir,
        }
        return f"""
            <div class="show-more-box">
                <a class="btn show-more-btn" href="/?{urllib.parse.urlencode(more_params, doseq=True)}">Rādīt vairāk</a>
                <span class="show-more-info">{rows_count} / {total_rows}</span>
            </div>
        """

    if total_rows:
        visible_count = min(
            rows_count,
            normalize_limit(limit_value) or rows_count,
        )
        return f"""
            <div class="show-more-box">
                <span class="show-more-info">{visible_count} / {rows_count}</span>
            </div>
        """

    return ""

def build_active_filter_chips(
    *,
    query_text,
    style_query_text,
    selected_workspaces,
    workspace_mode,
    selected_categories,
    category_mode,
    selected_local_families,
    kind_filter,
    local_audio_filter,
    limit_value,
    search_name,
    search_lyrics,
    search_prompt,
    search_marks,
    search_tags,
    flag_filter_value,
    tag_filter_value,
    selected_flag_filters,
    selected_tag_filters,
    selected_track_ids,
    selected_track_ids_value,
    sort_by,
    sort_dir,
):
    """Build the dismissible active-filter chips from one canonical state."""
    filter_state_params = {
        "q": query_text,
        "style_q": style_query_text,
        "workspace": selected_workspaces,
        "workspace_mode": workspace_mode if workspace_mode == "family_and" else "",
        "category_filter": selected_categories,
        "category_mode": category_mode if category_mode == "family_and" else "",
        "local_family_filter": selected_local_families,
        "kind_filter": str(kind_filter or "").strip(),
        "local_audio_filter": local_audio_filter,
        "search_name": "1" if search_name else "0",
        "search_lyrics": "1" if search_lyrics else "0",
        "search_prompt": "1" if search_prompt else "0",
        "search_marks": "1" if search_marks else "0",
        "search_tags": "1" if search_tags else "0",
        "flag_filter": flag_filter_value,
        "tag_filter": tag_filter_value,
        "track_ids": selected_track_ids_value,
        "sort_by": sort_by,
        "sort_dir": sort_dir,
    }

    def filter_state_url(remove_keys=(), overrides=None):
        params = dict(filter_state_params)
        for key in remove_keys:
            params.pop(str(key), None)
        for key, value in (overrides or {}).items():
            if value in (None, ""):
                params.pop(str(key), None)
            else:
                params[str(key)] = str(value)
        params = {
            key: value
            for key, value in params.items()
            if value not in (None, "")
        }
        encoded = urllib.parse.urlencode(params, doseq=True)
        return f"/?{encoded}" if encoded else "/"

    def filter_chip(label, chip_class, remove_keys=(), title="", href=""):
        clean_label = str(label or "").strip()
        accessible_label = title or clean_label
        return f"""
            <span class="ls-filter-chip ls-filter-chip-{esc(chip_class)}" title="{esc(accessible_label)}">
                <span class="ls-filter-chip-label">{esc(clean_label)}</span>
                <a
                    class="ls-filter-chip-remove"
                    href="{esc(href or filter_state_url(remove_keys=remove_keys))}"
                    aria-label="Remove {esc(accessible_label)} filter"
                    title="Remove this filter"
                >×</a>
            </span>
        """

    filter_chips = []
    for workspace_value in selected_workspaces:
        remaining_workspaces = [
            value for value in selected_workspaces
            if value.casefold() != workspace_value.casefold()
        ]
        filter_chips.append(filter_chip(
            f"Workspace: {workspace_value}",
            "neutral",
            title="Workspace",
            href=filter_state_url(overrides={
                "workspace": remaining_workspaces,
                "workspace_mode": (
                    workspace_mode if len(remaining_workspaces) >= 2 else ""
                ),
            }),
        ))

    if workspace_mode == "family_and":
        filter_chips.append(filter_chip(
            "Workspace: AND by Local family",
            "selected",
            title="Require the same Local family in every selected Workspace",
            href=filter_state_url(overrides={"workspace_mode": ""}),
        ))

    for family_value in selected_local_families:
        remaining_families = [
            value for value in selected_local_families
            if value.casefold() != family_value.casefold()
        ]
        filter_chips.append(filter_chip(
            f"Local family: {family_value}",
            "local",
            title="Confirmed Local family",
            href=filter_state_url(overrides={
                "local_family_filter": remaining_families,
            }),
        ))

    category_label_map = {
        "Song": "Song",
        "Instrumental": "Instrumental",
        "__instrumental_review__": "Instrumental to review",
        "__unclassified__": "Unclassified",
    }
    for category_value in selected_categories:
        remaining_categories = [
            value for value in selected_categories
            if value.casefold() != category_value.casefold()
        ]
        filter_chips.append(filter_chip(
            category_label_map.get(category_value, category_value),
            "category",
            title="Category",
            href=filter_state_url(overrides={
                "category_filter": remaining_categories,
                "category_mode": (
                    category_mode if len(remaining_categories) >= 2 else ""
                ),
            }),
        ))

    if category_mode == "family_and":
        filter_chips.append(filter_chip(
            "Category: AND by Local family",
            "selected",
            title="Require the same Local family in every selected Category",
            href=filter_state_url(overrides={"category_mode": ""}),
        ))

    type_label_map = {
        "__has_stems__": "Has Stems",
        "__liked__": "Liked",
        "__conflict_s_to_i__": "Legacy S→I conflicts",
        "__conflict_i_to_s__": "Legacy I→S conflicts",
        "__intent_s_to_i__": "Audit: Song → Instrumental",
        "__intent_i_to_s__": "Audit: Instrumental → Song",
        "__last_imported__": "Last imported Suno",
        "__unlinked_stems__": "Unlinked Stems",
    }
    if kind_filter:
        filter_chips.append(filter_chip(
            type_label_map.get(kind_filter, f"Type: {kind_filter}"),
            "type",
            ("kind_filter",),
        ))

    if local_audio_filter:
        filter_chips.append(filter_chip(
            "Local" if local_audio_filter == "with" else "Suno.com",
            "local",
            ("local_audio_filter",),
        ))

    if query_text:
        scope_labels = ["Track ID"]
        if search_name:
            scope_labels.append("Name")
        if search_lyrics:
            scope_labels.append("Lyrics")
        if search_prompt:
            scope_labels.append("Prompt")
        filter_chips.append(filter_chip(
            f"Search: {query_text}",
            "search",
            ("q",),
            f"Search in {', '.join(scope_labels)}",
        ))

    if style_query_text:
        filter_chips.append(filter_chip(
            f"Style: {style_query_text}",
            "search",
            ("style_q",),
        ))

    if search_marks:
        filter_chips.append(filter_chip(
            "Any ✶ mark",
            "mark",
            ("search_marks",),
            "At least one LS rating mark",
        ))

    if search_tags:
        filter_chips.append(filter_chip(
            "Any #tag",
            "tag",
            ("search_tags",),
            "At least one user tag",
        ))

    flag_label_map = {
        1: "1✶ Labs ritms",
        2: "2✶ Labs pavadījums",
        4: "3✶ Labs solo",
        8: "4✶ Interesants",
        16: "5✶ Uzmanību",
    }
    for mask in selected_flag_filters:
        remaining_flags = [
            value for value in selected_flag_filters if value != mask
        ]
        filter_chips.append(filter_chip(
            flag_label_map.get(mask, f"{mask}✶"),
            "mark",
            title="Required LS flag",
            href=filter_state_url(overrides={
                "flag_filter": ",".join(str(value) for value in remaining_flags),
            }),
        ))

    for tag in selected_tag_filters:
        remaining_tags = [
            value for value in selected_tag_filters
            if value.lower() != tag.lower()
        ]
        filter_chips.append(filter_chip(
            tag,
            "tag",
            title="Required user tag",
            href=filter_state_url(overrides={
                "tag_filter": ",".join(remaining_tags),
            }),
        ))

    if selected_track_ids:
        filter_chips.append(filter_chip(
            f"Selected: {len(selected_track_ids)}",
            "selected",
            ("track_ids", "selected_from_suno"),
            "Exact selected Track IDs",
        ))

    return filter_chips

def multi_filter_option(param_name, value, label, selected=False):
    """Render one reusable multi-select filter option button."""
    active_class = " active" if selected else ""
    return f"""
        <button
            type="button"
            class="library-multi-option{active_class}"
            data-multi-filter-param="{esc(param_name)}"
            data-multi-filter-value="{esc(value)}"
            aria-pressed="{'true' if selected else 'false'}"
        ><span class="library-multi-check" aria-hidden="true">{'✓' if selected else ''}</span><span>{esc(label)}</span></button>
    """

def build_workspace_and_local_family_controls(
    *,
    workspaces,
    selected_workspaces,
    workspace_mode,
    selected_local_families,
):
    """Build Workspace and confirmed Local family filter controls."""

    workspace_menu_items = [multi_filter_option(
        "workspace", "", "All workspaces", not selected_workspaces
    )]
    selected_workspace_keys = {value.casefold() for value in selected_workspaces}
    for row in workspaces:
        name = str(row["workspace"] or "").strip()
        count = int(row["count"] or 0)
        workspace_menu_items.append(multi_filter_option(
            "workspace",
            name,
            f"{name} ({count})",
            name.casefold() in selected_workspace_keys,
        ))

    if not selected_workspaces:
        workspace_summary = "All workspaces"
    elif len(selected_workspaces) == 1:
        workspace_summary = selected_workspaces[0]
    else:
        workspace_summary = f"{len(selected_workspaces)} workspaces"
    if workspace_mode == "family_and":
        workspace_summary += " · AND"

    workspace_mode_disabled = len(selected_workspaces) < 2
    workspace_mode_controls = f"""
        <div class="library-group-mode" aria-label="Workspace combination mode">
            <button type="button" class="library-group-mode-option{' active' if workspace_mode == 'or' else ''}" data-group-mode-param="workspace_mode" data-group-mode-value="or">OR</button>
            <button type="button" class="library-group-mode-option{' active' if workspace_mode == 'family_and' else ''}" data-group-mode-param="workspace_mode" data-group-mode-value="family_and" {'disabled' if workspace_mode_disabled else ''}>AND by Local family</button>
        </div>
    """

    confirmed_local_families = get_confirmed_local_family_filter_options()
    selected_family_keys = {
        value.casefold() for value in selected_local_families
    }
    local_family_menu_items = [multi_filter_option(
        "local_family_filter",
        "",
        f"All Local families ({len(confirmed_local_families)})",
        not selected_local_families,
    )]
    for item in confirmed_local_families:
        family_title = str(item.get("title") or "").strip()
        family_count = int(item.get("count") or 0)
        categories = " / ".join(item.get("categories") or [])
        suffix = f" · {categories}" if categories else ""
        local_family_menu_items.append(multi_filter_option(
            "local_family_filter",
            family_title,
            f"{family_title} ({family_count}){suffix}",
            family_title.casefold() in selected_family_keys,
        ))

    if not selected_local_families:
        local_family_summary = "All Local families"
    elif len(selected_local_families) == 1:
        local_family_summary = selected_local_families[0]
    else:
        local_family_summary = f"{len(selected_local_families)} Local families"

    return {
        "workspace_menu_items": workspace_menu_items,
        "workspace_summary": workspace_summary,
        "workspace_mode_controls": workspace_mode_controls,
        "local_family_menu_items": local_family_menu_items,
        "local_family_summary": local_family_summary,
    }

def build_audio_source_filter_options(local_audio_filter):
    """Render the visible Local/Suno.com source filter using the existing filter values."""
    normalized = str(local_audio_filter or "").strip().lower()
    if normalized not in {"with", "without"}:
        normalized = ""
    return "".join([
        f'<option value=""{" selected" if normalized == "" else ""}>All</option>',
        f'<option value="with"{" selected" if normalized == "with" else ""}>Local</option>',
        f'<option value="without"{" selected" if normalized == "without" else ""}>Suno.com</option>',
    ])


def build_category_and_type_controls(
    *,
    stats,
    selected_categories,
    category_mode,
    kind_filter,
):
    """Build Category multi-select and Type select control markup."""
    all_main_count = stats.get(
        "total_main_active",
        stats["total_active"] - stats["total_stems"],
    )
    category_choices = [
        (
            "Song",
            f'Songs ({stats.get("total_category_song", 0)})',
            stats.get("total_category_song", 0),
        ),
        (
            "Instrumental",
            f'Instrumental ({stats.get("total_category_instrumental", 0)})',
            stats.get("total_category_instrumental", 0),
        ),
        (
            "SongOrInstrumental",
            f'SongOrInstrumental ({stats.get("total_category_uncertain", 0)})',
            stats.get("total_category_uncertain", 0),
        ),
        (
            "__instrumental_review__",
            f'Instrumental to review ({stats.get("total_instrumental_review", 0)})',
            stats.get("total_instrumental_review", 0),
        ),
        (
            "__unclassified__",
            f'Unclassified ({stats.get("total_category_unclassified", 0)})',
            stats.get("total_category_unclassified", 0),
        ),
    ]
    selected_category_keys = {
        value.casefold() for value in selected_categories
    }
    category_menu_items = [multi_filter_option(
        "category_filter",
        "",
        f"All categories ({all_main_count})",
        not selected_categories,
    )]
    for value, label, count in category_choices:
        if not count:
            continue
        category_menu_items.append(multi_filter_option(
            "category_filter",
            value,
            label,
            value.casefold() in selected_category_keys,
        ))

    category_label_map = {
        "Song": "Song",
        "Instrumental": "Instrumental",
        "SongOrInstrumental": "SongOrInstrumental",
        "__instrumental_review__": "Instrumental to review",
        "__unclassified__": "Unclassified",
    }
    if not selected_categories:
        category_summary = "All categories"
    elif len(selected_categories) == 1:
        category_summary = category_label_map.get(
            selected_categories[0],
            selected_categories[0],
        )
    else:
        category_summary = f"{len(selected_categories)} categories"
    if category_mode == "family_and":
        category_summary += " · AND"

    category_mode_disabled = len(selected_categories) < 2
    category_mode_controls = f"""
        <div class="library-group-mode" aria-label="Category combination mode">
            <button type="button" class="library-group-mode-option{' active' if category_mode == 'or' else ''}" data-group-mode-param="category_mode" data-group-mode-value="or">OR</button>
            <button type="button" class="library-group-mode-option{' active' if category_mode == 'family_and' else ''}" data-group-mode-param="category_mode" data-group-mode-value="family_and" {'disabled' if category_mode_disabled else ''}>AND by Local family</button>
        </div>
    """

    kind_filter_options = [
        f'<option value="" data-hotkey="a" {selected_attr(kind_filter, "")}>All types ({all_main_count})</option>',
    ]
    for type_row in get_ui_type_counts():
        ui_type = str(type_row["ui_type"] or "").strip()
        if not ui_type or ui_type in ("Song", "Instrumental"):
            continue
        kind_filter_options.append(
            f'<option value="{esc(ui_type)}" {selected_attr(kind_filter, ui_type)}>{esc(ui_type)} ({int(type_row["count"] or 0)})</option>'
        )
    kind_filter_options.extend([
        f'<option value="__has_stems__" data-hotkey="m" {selected_attr(kind_filter, "__has_stems__")}>Has Stems — {stats.get("total_has_stems", 0)} tracks / {stats.get("total_local_stem_files", 0)} files</option>',
        f'<option value="__liked__" data-hotkey="l" {selected_attr(kind_filter, "__liked__")}>Liked ({stats.get("total_liked", 0)})</option>',
    ])

    review_s_to_i_count = stats.get("total_conflict_s_to_i", 0)
    review_i_to_s_count = stats.get("total_conflict_i_to_s", 0)
    intent_s_to_i_count = stats.get("total_intent_s_to_i", 0)
    intent_i_to_s_count = stats.get("total_intent_i_to_s", 0)
    if intent_s_to_i_count:
        kind_filter_options.append(
            f'<option value="__intent_s_to_i__" {selected_attr(kind_filter, "__intent_s_to_i__")}>Audit: Song → Instrumental ({intent_s_to_i_count})</option>'
        )
    if intent_i_to_s_count:
        kind_filter_options.append(
            f'<option value="__intent_i_to_s__" {selected_attr(kind_filter, "__intent_i_to_s__")}>Audit: Instrumental → Song ({intent_i_to_s_count})</option>'
        )
    if review_s_to_i_count:
        kind_filter_options.append(
            f'<option value="__conflict_s_to_i__" {selected_attr(kind_filter, "__conflict_s_to_i__")}>Legacy S→I conflicts ({review_s_to_i_count})</option>'
        )
    if review_i_to_s_count:
        kind_filter_options.append(
            f'<option value="__conflict_i_to_s__" {selected_attr(kind_filter, "__conflict_i_to_s__")}>Legacy I→S conflicts ({review_i_to_s_count})</option>'
        )
    last_imported_count = len(get_last_imported_suno_ids())
    if last_imported_count:
        kind_filter_options.append(
            f'<option value="__last_imported__" data-hotkey="" {selected_attr(kind_filter, "__last_imported__")}>Last imported Suno ({last_imported_count})</option>'
        )

    return {
        "category_menu_items": category_menu_items,
        "category_summary": category_summary,
        "category_mode_controls": category_mode_controls,
        "kind_filter_options_html": "".join(kind_filter_options),
    }

def build_filter_form_support_markup(
    *,
    selected_workspaces,
    selected_categories,
    selected_local_families,
    db_refresh,
):
    """Build hidden multi-filter fields and optional DB refresh feedback."""
    workspace_hidden_inputs = "".join(
        f'<input type="hidden" name="workspace" value="{esc(value)}">'
        for value in selected_workspaces
    )
    category_hidden_inputs = "".join(
        f'<input type="hidden" name="category_filter" value="{esc(value)}">'
        for value in selected_categories
    )
    local_family_hidden_inputs = "".join(
        f'<input type="hidden" name="local_family_filter" value="{esc(value)}">'
        for value in selected_local_families
    )

    refresh_message = ""
    if db_refresh == "ok":
        latest_summary = get_latest_refresh_summary()
        latest_summary_html = ""
        if latest_summary:
            latest_summary_html = f"""
                <pre class="refresh-summary">{esc(latest_summary)}</pre>
            """
        refresh_message = f"""
            <div class="refresh-message ok" role="status">
                <div class="refresh-message-head">
                    <strong>DB refresh completed.</strong>
                    <button type="button" class="refresh-message-close" aria-label="Aizvērt DB refresh rezultātu" title="Aizvērt" data-db-refresh-close="1">×</button>
                </div>
                {latest_summary_html}
            </div>
        """
    elif db_refresh == "error":
        refresh_message = """
            <div class="refresh-message error" role="alert">
                <div class="refresh-message-head">
                    <span>DB refresh failed. Check PowerShell output.</span>
                    <button type="button" class="refresh-message-close" aria-label="Aizvērt DB refresh rezultātu" title="Aizvērt" data-db-refresh-close="1">×</button>
                </div>
            </div>
        """

    return {
        "workspace_hidden_inputs": workspace_hidden_inputs,
        "category_hidden_inputs": category_hidden_inputs,
        "local_family_hidden_inputs": local_family_hidden_inputs,
        "refresh_message": refresh_message,
    }

def build_finder_search_controls_state(
    *,
    query,
    style_query,
    local_audio_filter,
    search_name,
    search_lyrics,
    search_prompt,
    search_marks,
    search_tags,
    flag_filter,
    tag_filter,
):
    """Normalize Finder search controls and build their display values."""
    query_escaped = esc(query)
    style_query_escaped = esc(style_query)

    normalized_local_audio_filter = str(local_audio_filter or "").strip().lower()
    if normalized_local_audio_filter not in {"with", "without"}:
        normalized_local_audio_filter = ""
    local_audio_filter_escaped = esc(normalized_local_audio_filter)

    normalized_search_name = normalize_search_scope_flag(search_name, True)
    normalized_search_lyrics = normalize_search_scope_flag(search_lyrics, False)
    normalized_search_prompt = normalize_search_scope_flag(search_prompt, False)
    normalized_search_marks = normalize_search_scope_flag(search_marks, False)
    normalized_search_tags = normalize_search_scope_flag(search_tags, False)

    selected_flag_filters = normalize_flag_filter(flag_filter)
    selected_tag_filters = normalize_tag_filter(tag_filter)
    flag_filter_value = ",".join(str(mask) for mask in selected_flag_filters)
    tag_filter_value = ",".join(selected_tag_filters)

    flag_token_by_mask = {1: "1+*", 2: "2+*", 4: "3+*", 8: "4+*", 16: "5+*"}
    finder_search_parts = []
    if str(query or "").strip():
        finder_search_parts.append(str(query).strip())
    if normalized_search_marks and not selected_flag_filters:
        finder_search_parts.append("0+*")
    finder_search_parts.extend(
        flag_token_by_mask[mask]
        for mask in selected_flag_filters
        if mask in flag_token_by_mask
    )
    finder_search_parts.extend(selected_tag_filters)

    return {
        "query_escaped": query_escaped,
        "style_query_escaped": style_query_escaped,
        "local_audio_filter": normalized_local_audio_filter,
        "local_audio_filter_escaped": local_audio_filter_escaped,
        "search_name": normalized_search_name,
        "search_lyrics": normalized_search_lyrics,
        "search_prompt": normalized_search_prompt,
        "search_marks": normalized_search_marks,
        "search_tags": normalized_search_tags,
        "selected_flag_filters": selected_flag_filters,
        "selected_tag_filters": selected_tag_filters,
        "flag_filter_value": flag_filter_value,
        "tag_filter_value": tag_filter_value,
        "finder_search_display_escaped": esc(" ".join(finder_search_parts)),
        "search_name_checked": "checked" if normalized_search_name else "",
        "search_lyrics_checked": "checked" if normalized_search_lyrics else "",
        "search_prompt_checked": "checked" if normalized_search_prompt else "",