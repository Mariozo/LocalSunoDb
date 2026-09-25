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
        "search_marks_checked": "checked" if normalized_search_marks else "",
        "search_tags_checked": "checked" if normalized_search_tags else "",
    }

def build_ls_elza_view_context(
    *,
    query_text,
    style_query_text,
    search_name,
    search_lyrics,
    search_prompt,
    search_marks,
    search_tags,
    selected_workspaces,
    workspace_mode,
    selected_categories,
    category_mode,
    selected_local_families,
    kind_filter,
    total_rows,
    loaded_row_count,
    limit_value,
    saved_views,
    selected_track_ids,
    selection_view_active,
    local_audio_filter,
    family_group_track_ids,
):
    """Build the read-only LS Elza context for the current Finder view."""
    type_filter_labels = {
        "": "All",
        "__has_stems__": "Has Stems",
        "__unlinked_stems__": "Unlinked Stems",
        "__liked__": "Liked",
        "__last_imported__": "Last imported",
        "__conflict_s_to_i__": "Song → Instrumental conflicts",
        "__conflict_i_to_s__": "Instrumental → Song conflicts",
    }
    normalized_kind_filter = str(kind_filter or "").strip()

    return {
        "view_name": "tracks",
        "search_text": query_text or None,
        "style_search_text": style_query_text or None,
        "search_fields": [
            label
            for enabled, label in [
                (search_name, "Name"),
                (search_lyrics, "Lyrics"),
                (search_prompt, "Prompt"),
                (search_marks, "✶"),
                (search_tags, "#tag"),
            ]
            if enabled
        ],
        "workspace_filter": (
            selected_workspaces[0]
            if len(selected_workspaces) == 1 else None
        ),
        "workspace_filters": selected_workspaces,
        "workspace_mode": workspace_mode,
        "category_filter": (
            selected_categories[0]
            if len(selected_categories) == 1 else None
        ),
        "category_filters": selected_categories,
        "category_mode": category_mode,
        "local_family_filter": (
            selected_local_families[0]
            if len(selected_local_families) == 1 else None
        ),
        "local_family_filters": selected_local_families,
        "type_filter": normalized_kind_filter or None,
        "type_filter_label": type_filter_labels.get(
            normalized_kind_filter,
            normalized_kind_filter or "All",
        ),
        "result_count": (None if total_rows is None else int(total_rows or 0)),
        "loaded_row_count": int(loaded_row_count or 0),
        "row_limit": limit_value,
        "saved_views": [
            {
                "name": item.get("name"),
                "view_url": (
                    f"/?{item.get('query')}" if item.get("query") else "/"
                ),
            }
            for item in saved_views
        ],
        "filters": {
            "track_ids_filter_count": len(selected_track_ids),
            "selection_view_active": bool(selection_view_active),
            "local_audio_filter": local_audio_filter or None,
            "family_group_match_count": (
                len(family_group_track_ids)
                if family_group_track_ids is not None else None
            ),
        },
    }

def load_render_page_result_state(
    *,
    query,
    style_query,
    selected_workspaces,
    workspace_mode,
    kind_filter,
    selected_categories,
    category_mode,
    selected_local_families,
    local_audio_filter,
    limit_value,
    search_name,
    search_lyrics,
    search_prompt,
    search_marks,
    search_tags,
    flag_filter,
    tag_filter,
    track_ids_filter,
    sort_by,
    sort_dir,
):
    """Load Finder rows and render-time lookup data for one normalized view."""
    family_group_track_ids = None
    if workspace_mode == "family_and" or category_mode == "family_and":
        family_group_track_ids = get_local_family_group_match_track_ids(
            workspace_values=(
                selected_workspaces if workspace_mode == "family_and" else []
            ),
            category_values=(
                selected_categories if category_mode == "family_and" else []
            ),
        )

    shared_filters = {
        "query": query,
        "style_query": style_query,
        "workspace": selected_workspaces,
        "kind_filter": kind_filter,
        "category_filter": selected_categories,
        "local_family_filter": selected_local_families,
        "local_audio_filter": local_audio_filter,
        "search_name": search_name,
        "search_lyrics": search_lyrics,
        "search_prompt": search_prompt,
        "search_marks": search_marks,
        "search_tags": search_tags,
        "flag_filter": flag_filter,
        "tag_filter": tag_filter,
        "track_ids_filter": track_ids_filter,
        "family_group_track_ids": family_group_track_ids,
    }
    # Keep the visible-row query limited. COUNT(*) OVER() made SQLite process
    # and sort the entire large result set before LIMIT, which slowed Cover and
    # All types disproportionately. The narrow count query is separate again.
    total_rows = count_tracks(**shared_filters)
    rows = search_tracks(
        **shared_filters,
        limit_value=limit_value,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    stem_counts = get_stem_counts_for_track_ids(
        [row["id"] for row in rows]
    )
    confirmed_local_audio_paths = get_confirmed_local_audio_paths_for_render(
        rows
    )
    local_audio_paths = get_best_local_audio_paths_for_render(
        rows,
        confirmed_paths=confirmed_local_audio_paths,
    )

    return {
        "family_group_track_ids": family_group_track_ids,
        "total_rows": total_rows,
        "rows": rows,
        "stem_counts": stem_counts,
        "confirmed_local_audio_paths": confirmed_local_audio_paths,
        "local_audio_paths": local_audio_paths,
    }

def build_filter_navigation_html(
    *,
    query,
    style_query,
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
    saved_views,
    total_rows,
    rows_count,
    sort_by,
    sort_dir,
):
    """Build the active-filter bar and Show more navigation from one state."""
    filter_chips = build_active_filter_chips(
        query_text=query_text,
        style_query_text=style_query_text,
        selected_workspaces=selected_workspaces,
        workspace_mode=workspace_mode,
        selected_categories=selected_categories,
        category_mode=category_mode,
        selected_local_families=selected_local_families,
        kind_filter=kind_filter,
        local_audio_filter=local_audio_filter,
        limit_value=limit_value,
        search_name=search_name,
        search_lyrics=search_lyrics,
        search_prompt=search_prompt,
        search_marks=search_marks,
        search_tags=search_tags,
        flag_filter_value=flag_filter_value,
        tag_filter_value=tag_filter_value,
        selected_flag_filters=selected_flag_filters,
        selected_tag_filters=selected_tag_filters,
        selected_track_ids=selected_track_ids,
        selected_track_ids_value=selected_track_ids_value,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    active_search_html, clear_all_html = render_active_filter_bar_html(
        filter_chips=filter_chips,
        saved_views=saved_views,
        total_rows=total_rows,
        limit_value=limit_value,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    show_more_html = render_show_more_html(
        rows_count=rows_count,
        total_rows=total_rows,
        limit_value=limit_value,
        query=query,
        style_query=style_query,
        selected_workspaces=selected_workspaces,
        workspace_mode=workspace_mode,
        selected_categories=selected_categories,
        category_mode=category_mode,
        selected_local_families=selected_local_families,
        kind_filter=kind_filter,
        local_audio_filter=local_audio_filter,
        search_name=search_name,
        search_lyrics=search_lyrics,
        search_prompt=search_prompt,
        search_marks=search_marks,
        search_tags=search_tags,
        flag_filter_value=flag_filter_value,
        tag_filter_value=tag_filter_value,
        selected_track_ids_value=selected_track_ids_value,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    return active_search_html, clear_all_html, show_more_html

def build_track_thumbnail_html(row, duration_display):
    """Build one Library-row thumbnail from image URLs already stored in the DB."""
    # Do not guess CDN filename variants and do not call /suno-image for every
    # row: that created thousands of failed network requests.
    image_candidates = []

    def add_image_candidate(value):
        value = str(value or "").strip()
        if value and value not in image_candidates:
            image_candidates.append(value)

    if "raw_image_url" in row.keys():
        add_image_candidate(row["raw_image_url"])

    if "raw_image_large_url" in row.keys():
        add_image_candidate(row["raw_image_large_url"])

    image_url = image_candidates[0] if image_candidates else ""
    image_large_url = image_candidates[-1] if image_candidates else ""
    image_fallbacks = "|".join(image_candidates[1:])

    duration_badge_html = (
        '<span class="thumb-duration-badge duration-sort-trigger" '
        f'title="Sort by duration">{esc(duration_display)}</span>'
        if duration_display else ""
    )

    if image_url:
        return (
            f'<span class="thumb-link" data-large-cover="{esc(image_large_url or image_url)}" '
            'title="Klikšķis: Play/Pause • Labais klikšķis: atvērt attēlu">'
            f'<img class="track-thumb" src="{esc(image_url)}" '
            f'data-fallbacks="{esc(image_fallbacks)}" alt="cover" loading="lazy" '
            'decoding="async" fetchpriority="low" onerror="tryNextThumb(this);">'
            f'{duration_badge_html}'
            '</span>'
        )

    return f'<span class="thumb-placeholder">{duration_badge_html}</span>'

def build_library_secondary_html(
    duration_display,
    workspace_text,
    created_display,
):
    """Build the compact duration, Workspace and created line for one Library row."""
    parts = []
    if duration_display:
        parts.append(
            f'<span class="ls-library-secondary-item">{esc(duration_display)}</span>'
        )
    if workspace_text:
        parts.append(
            f'<span class="ls-library-secondary-item">{esc(workspace_text)}</span>'
        )
    if created_display:
        parts.append(
            f'<span class="ls-library-secondary-item">{esc(created_display)}</span>'
        )

    if not parts:
        return ""

    return (
        '<div class="ls-library-secondary">'
        + '<span class="ls-library-secondary-dot">·</span>'.join(parts)
        + '</div>'
    )

def build_library_table_rows(
    *,
    rows,
    stem_counts,
    confirmed_local_audio_paths,
    local_audio_paths,
    selection_view_active,
    kind_filter,
    row_index_start=0,
    include_empty_state=True,
):
    """Build all Library result rows without changing their existing HTML or behavior."""
    table_rows = []
    previous_workspace = None
    local_family_titles = get_track_local_family_titles()

    title_group_counts = {}
    title_group_seen = {}

    for row in rows:
        title_key = (row["title"] or "", row["workspace"] or "")
        title_group_counts[title_key] = title_group_counts.get(title_key, 0) + 1

    for index, row in enumerate(rows, start=int(row_index_start or 0) + 1):
        track_id = row["id"]
        local_family_title = local_family_titles.get(str(track_id or "").strip().lower(), "")
        title = row["title"]
        title_key = (title or "", row["workspace"] or "")
        title_group_seen[title_key] = title_group_seen.get(title_key, 0) + 1
        title_number = title_group_seen[title_key]

        title_clean = str(title or "").strip()

        if not title_clean:
            # Some Suno exports contain tracks with an empty title.
            # Keep the row usable by showing a visible, clickable placeholder.
            display_title = "[No title]"
        elif title_group_counts.get(title_key, 0) > 1:
            display_title = f"{title_clean} ({title_number})"
        else:
            display_title = title_clean

        suno_url = make_suno_url(track_id)
        audio_url = row["audio_url"]
        workspace_text = row["workspace"] or ""

        group_class = ""
        if index > 1 and workspace_text != previous_workspace:
            group_class = " workspace-group-start"

        previous_workspace = workspace_text

        created_display = format_created_at(row["created_at"])
        created_sort = created_sort_value(row["created_at"])

        duration_display = format_duration(row["duration"])
        duration_sort_source = row["sort_duration_seconds"] if "sort_duration_seconds" in row.keys() else row["duration"]
        duration_sort = duration_sort_value(duration_sort_source)

        style_text = row["style"] if "style" in row.keys() else ""
        style_short = shorten_text(style_text, 120)

        kind_text = row["kind"] if "kind" in row.keys() else ""
        main_category_text = str(row["proposed_main_category"] if "proposed_main_category" in row.keys() and row["proposed_main_category"] else (row["main_category"] if "main_category" in row.keys() else kind_text)).strip()
        if main_category_text not in [
            "Song", "Instrumental", "SongOrInstrumental"
        ]:
            main_category_text = kind_text if kind_text in ["Song", "Instrumental"] else ""
        main_category_confidence_label = str(row["main_category_confidence_label"] if "main_category_confidence_label" in row.keys() else "").strip()
        if not main_category_confidence_label:
            main_category_confidence_label = "weak"
        main_category_confirmed = (
            str(
                row["main_category_review_group"]
                if "main_category_review_group" in row.keys() else ""
            ).strip() == "manual_toggle"
        )
        user_rating = 0
        try:
            user_rating = int(row["user_rating"] if "user_rating" in row.keys() and row["user_rating"] not in [None, ""] else 0)
        except Exception:
            user_rating = 0
        user_rating = max(0, min(5, user_rating))

        user_marks = 0
        try:
            user_marks = int(row["user_marks"] if "user_marks" in row.keys() and row["user_marks"] not in [None, ""] else 0)
        except Exception:
            user_marks = 0
        user_marks = max(0, min(31, user_marks))

        user_tags = normalize_user_tags_text(row["user_tags"] if "user_tags" in row.keys() else "")

        liked_value = row["is_liked"] if "is_liked" in row.keys() else 0
        like_text = format_like(liked_value)
        like_sort = like_sort_value(liked_value)
        like_is_on = normalize_bool_liked(liked_value)
        like_button_text = "👍" if like_is_on else "♡"
        like_button_title = "Remove Like" if like_is_on else "Add Like"
        like_button_class = " liked" if like_is_on else ""

        bpm_text = str(row["bpm"] if "bpm" in row.keys() else "").strip()
        if bpm_text.lower() in ["none", "null", "nan"]:
            bpm_text = ""

        model_text = str(row["major_model_version"] if "major_model_version" in row.keys() else "").strip()
        if not model_text or model_text.lower() in ["none", "null", "nan"]:
            model_text = str(row["model_version"] if "model_version" in row.keys() else "").strip()

        if model_text.lower() in ["none", "null", "nan"]:
            model_text = ""

        # Do not show internal Suno model_name values like chirp/chirp-crow in the title row.
        # The visible badge should be the user-facing version, for example v5 or v5.5.
        if model_text and not model_text.lower().startswith("v"):
            model_text = ""

        created_for_model_guess = str(row["created_at"] if "created_at" in row.keys() else "").strip()
        guessed_latest_model = False
        if not model_text:
            if created_for_model_guess >= "2026-03-26":
                model_text = "v5.5?"
                guessed_latest_model = True
            else:
                model_text = "—"

        stem_count = int(
            stem_counts.get(str(track_id or "").strip().lower(), 0) or 0
        )
        has_linked_stems = stem_count > 0

        prompt_text = str(
            row["prompt"] if "prompt" in row.keys() else ""
        )
        lyrics_text = str(
            row["lyrics"] if "lyrics" in row.keys() else ""
        )
        style_text = str(style_text or "")

        text_preview_field = ""
        text_preview_label = ""
        text_preview_text = ""
        for field_name, field_label, field_text in [
            ("lyrics", "Lyrics", lyrics_text),
            ("prompt", "Prompt", prompt_text),
            ("style", "Style", style_text),
        ]:
            if str(field_text or "").strip():
                text_preview_field = field_name
                text_preview_label = field_label
                text_preview_text = str(field_text or "")
                break

        prompt_inline_html = ""
        if text_preview_text:
            prompt_inline_html = (
                f'<button type="button" '
                f'class="title-prompt-inline text-field-trigger '
                f'text-field-{esc(text_preview_field)}" '
                f'data-track-id="{esc(track_id)}" '
                f'data-track-title="{esc(display_title)}" '
                f'data-text-field="{esc(text_preview_field)}" '
                f'data-text-label="{esc(text_preview_label)}">'
                f'<span class="title-text-field-label">'
                f'{esc(text_preview_label)}</span>'
                f'<span class="title-text-field-preview">'
                f'{esc(shorten_text(text_preview_text, 260))}</span>'
                f'</button>'
            )

        # v4.19: BPM is first after title. Missing BPM is shown as "- - Bmp".
        bpm_display_text = f"{bpm_text} Bmp" if bpm_text else "- - Bmp"
        bpm_badge_class = "bpm-badge bpm-badge-known" if bpm_text else "bpm-badge bpm-badge-empty"
        bpm_inline_html = f'<span class="{bpm_badge_class}">{esc(bpm_display_text)}</span>'

        audit_recommended_action = str(
            row["audit_recommended_action"]
            if "audit_recommended_action" in row.keys() else ""
        ).strip()
        row_is_audit_candidate = (
            audit_recommended_action == "review_category_conflict"
        )
        audit_filter_active = kind_filter in {
            "__intent_s_to_i__", "__intent_i_to_s__"
        }

        title_meta_parts = []
        if main_category_text in ["Song", "Instrumental"]:
            main_badge_class = main_category_badge_class(main_category_text, main_category_confidence_label)
            main_badge_title = f"Main category: {main_category_text}; confidence: {main_category_confidence_label}"
            main_badge_text = main_category_text
            if row_is_audit_candidate and audit_filter_active:
                main_badge_text = f"Keep {main_category_text}"
                main_badge_title += f". Keep {main_category_text} and mark reviewed"
            elif not main_category_confirmed:
                main_badge_title += f". Click to confirm {main_category_text}"
            else:
                main_badge_title += ". Click to switch Song / Instrumental"
            title_meta_parts.append(
                f'<button type="button" class="title-badge {esc(main_badge_class)} main-category-toggle-btn" '
                f'data-track-id="{esc(track_id)}" data-category="{esc(main_category_text)}" '
                f'data-confirmed="{"true" if main_category_confirmed else "false"}" '
                f'title="{esc(main_badge_title)}">{esc(main_badge_text)}</button>'
            )
        elif main_category_text == "SongOrInstrumental":
            title_meta_parts.append(
                '<button type="button" class="title-badge main-category-badge '
                'main-category-uncertain main-category-toggle-btn" '
                f'data-track-id="{esc(track_id)}" '
                'data-category="SongOrInstrumental" '
                'data-confirmed="false" '
                'title="Category is uncertain. Click to confirm Song; click again to switch to Instrumental">'
                'SongOrInstrumental</button>'
            )

        if row_is_audit_candidate:
            audit_intent_label = str(
                row["audit_intent_label"]
                if "audit_intent_label" in row.keys() else ""
            ).strip()
            audit_confidence = str(
                row["audit_intent_confidence"]
                if "audit_intent_confidence" in row.keys() else ""
            ).strip()
            audit_rule = str(
                row["audit_rule_code"]
                if "audit_rule_code" in row.keys() else ""
            ).strip()
            try:
                audit_score = int(row["audit_intent_score"] or 0)
            except Exception:
                audit_score = 0
            try:
                audit_evidence = json.loads(
                    str(row["audit_evidence_json"] or "[]")
                )
                if not isinstance(audit_evidence, list):
                    audit_evidence = []
            except (TypeError, ValueError, json.JSONDecodeError):
                audit_evidence = []
            audit_title_parts = [
                f"Intent audit proposes {audit_intent_label or 'review'}",
                f"confidence {audit_confidence or 'unknown'}",
                f"score {audit_score}%",
            ]
            if audit_rule:
                audit_title_parts.append(f"rule {audit_rule}")
            if audit_evidence:
                audit_title_parts.append(
                    "evidence " + ", ".join(str(item) for item in audit_evidence)
                )
            title_meta_parts.append(
                f'<button type="button" class="title-badge intent-audit-badge intent-audit-accept-btn" '
                f'data-track-id="{esc(track_id)}" '
                f'data-intent-category="{esc(audit_intent_label)}" '
                f'title="{esc("; ".join(audit_title_parts))}. Click to change to {esc(audit_intent_label)}">'
                f'Change → {esc(audit_intent_label or "Review")} · {audit_score}%'
                f'</button>'
            )

        for badge_text, badge_class in detect_suno_ui_badges(
            title=title,
            kind=kind_text,
            style=style_text,
            prompt=prompt_text,
            lyrics=row["lyrics"] if "lyrics" in row.keys() else "",
        ):
            if badge_text in ["Song", "Instrumental"]:
                continue
            title_meta_parts.append(
                f'<span class="title-badge suno-ui-badge suno-ui-badge-{esc(badge_class)}">{esc(badge_text)}</span>'
            )
        if local_family_title:
            title_meta_parts.append(
                f'<span class="title-badge ls-local-family-badge" '
                f'title="Local Family: {esc(local_family_title)}">LocF</span>'
            )
        like_button_class = "liked" if like_is_on else ""
        like_button_title = "Remove Like" if like_is_on else "Add Like"
        title_meta_parts.append(
            f'<button type="button" class="like-toggle-btn title-like-badge {like_button_class}" '
            f'data-track-id="{esc(track_id)}" data-liked="{esc("true" if like_is_on else "false")}" '
            f'title="{esc(like_button_title)}">{like_thumb_svg()}</button>'
        )
        if has_linked_stems:
            title_meta_parts.append(f'<span class="title-badge stems-title-badge">Stems {stem_count}</span>')
        if user_marks:
            mark_text = " ".join(["✶" for _ in user_mark_labels(user_marks)])
            mark_title = ", ".join(user_mark_labels(user_marks))
            title_meta_parts.append(f'<span class="title-badge user-rating-badge" title="{esc(mark_title)}">{esc(mark_text)}</span>')
        if user_tags:
            for tag in [x.strip() for x in user_tags.split(",") if x.strip()][:4]:
                title_meta_parts.append(f'<span class="title-badge user-tag-badge" data-user-tag="{esc(tag if tag.startswith("#") else "#" + tag)}">{esc(tag if tag.startswith("#") else "#" + tag)}</span>')
        if model_text:
            if model_text.lower() == "v5.5":
                model_badge_class = "model-badge-red"
            elif guessed_latest_model:
                model_badge_class = "model-badge-guess"
            elif model_text == "—":
                model_badge_class = "model-badge-empty"
            else:
                model_badge_class = "model-badge-green"
            title_meta_parts.append(f'<span class="title-badge model-badge {model_badge_class}">{esc(model_text)}</span>')
        title_meta_html = ""
        if title_meta_parts:
            title_meta_html = '<div class="title-meta-line"><span class="title-meta">' + " ".join(title_meta_parts) + '</span></div>'

        # v5.21: keep important Library metadata inside the Suno-style track block.
        # The old table cells remain in the DOM for sorting and compatibility,
        # but the visible row no longer needs separate Workspace/Created columns.
        library_secondary_html = build_library_secondary_html(
            duration_display,
            workspace_text,
            created_display,
        )

        prompt_preview_line_html = ""
        if prompt_inline_html:
            prompt_preview_line_html = (
                '<div class="ls-library-text-preview">'
                + prompt_inline_html
                + '</div>'
            )

        style_under_title_html = ""

        thumbnail_html = build_track_thumbnail_html(
            row,
            duration_display,
        )
        player_cover_url = str(
            (row["raw_image_url"] if "raw_image_url" in row.keys() else "")
            or (row["raw_image_large_url"] if "raw_image_large_url" in row.keys() else "")
            or ""
        ).strip()
        player_cover_full_url = str(
            (row["raw_image_large_url"] if "raw_image_large_url" in row.keys() else "")
            or (row["raw_image_url"] if "raw_image_url" in row.keys() else "")
            or ""
        ).strip()

        resolved_local_audio = str(local_audio_paths.get(str(track_id or "").lower()) or "").strip()
        local_wav = resolved_local_audio if resolved_local_audio.lower().endswith(".wav") else ""
        local_mp3 = resolved_local_audio if resolved_local_audio.lower().endswith(".mp3") else ""
        compare_local_wav = ""
        if local_wav:
            try:
                candidate_obj = Path(local_wav)
                if candidate_obj.exists() and candidate_obj.is_file():
                    compare_local_wav = str(candidate_obj)
            except Exception:
                compare_local_wav = ""

        # Play colour is a DB-link status, not a filename guess.  The broader
        # resolver above may still help Compare, but it must not turn Play black.
        has_confirmed_local_audio = (
            str(track_id or "").lower() in confirmed_local_audio_paths
        )

        # Local WAV resolution stays available to the Player compare flow.
        # Row-level Compare is intentionally not rendered in v2.16.
        local_links = []
        db_track_checked_attr = " checked" if selection_view_active else ""

        audio_button = ""
        compare_button = ""
        stems_button = ""

        if has_linked_stems:
            stems_button = f"""
                <button
                    type="button"
                    class="small-action stems-btn"
                    data-track-id="{esc(track_id)}"
                    title="Open local stem player"
                >Stems {stem_count}</button>
            """

        if has_linked_stems:
            play_type_sort = "3 Play Stems"
            play_button_title = "Play Suno audio with linked stems"
            play_status_marker_class = "has-stems"
            play_status_marker_title = (
                "Ir Stems — dziesmai ir reāli piesaistīti lokālie Stem audio faili. "
                "Tas ir tas pats stāvoklis, kuru iepriekš rādīja zaļā Play poga."
            )
        elif has_confirmed_local_audio:
            play_type_sort = "2 Play Local"
            play_button_title = "Play Suno audio · confirmed local audio available"
            play_status_marker_class = "has-local"
            play_status_marker_title = (
                "Suno + lokālais audio — pieejams Suno audio un apstiprināts "
                "lokālais audio fails, bet nav piesaistītu lokālo Stem failu."
            )
        else:
            play_type_sort = "1 Play Suno"
            play_button_title = "Play Suno audio · no confirmed local audio"
            play_status_marker_class = "suno-only"
            play_status_marker_title = (
                "Tikai Suno — nav piesaistīta apstiprināta lokālā audio faila "
                "un nav lokālo Stem failu."
            )

        play_status_marker_html = (
            f'<span class="ls-play-status-marker {play_status_marker_class}" '
            f'title="{esc(play_status_marker_title)}" aria-label="{esc(play_status_marker_title)}"></span>'
        )

        if track_id:
            audio_button = f"""
                <button
                    type="button"
                    class="play-btn ls-cover-play-btn{' has-stems-play' if has_linked_stems else (' no-local-play' if not has_confirmed_local_audio else '')}"
                    data-audio="{esc(audio_url)}"
                    data-track-id="{esc(track_id)}"
                    data-suno-url="{esc(suno_url)}"
                    data-title="{esc(display_title)}"
                    data-cover="{esc(player_cover_url)}"
                    data-cover-full="{esc(player_cover_full_url)}"
                    data-local-path="{esc(compare_local_wav)}"
                    data-local-audio="{esc(build_local_playback_url(track_id, has_confirmed_local_audio))}"
                    data-has-stems="{esc('true' if has_linked_stems else 'false')}"
                    data-has-local-audio="{esc('true' if has_confirmed_local_audio else 'false')}"
                    title="{esc(play_button_title)}"
                    aria-label="{esc(play_button_title)}"
                >▶</button>
            """

        table_rows.append(f"""
            <tr
                class="track-row{group_class}{' has-stems' if has_linked_stems else ''}"
                data-track-id="{esc(track_id)}"
                data-title="{esc(title_clean or '[No title]')}"
                data-workspace="{esc(workspace_text)}"
                data-main-category="{esc(main_category_text)}"
                data-kind="{esc(kind_text)}"
                data-marks="{user_marks}"
                data-user-tags="{esc(user_tags)}"
                data-local-family="{esc(local_family_title)}"
            >
                <td class="num">{index}</td>

                <td class="select-cell"></td>

                <td class="title-cell" data-sort="{esc(lv_sort_key(display_title))}" title="Track ID: {esc(track_id)}">
                    <div class="title-with-thumb">
                        <div class="ls-track-cover-control">
                            {play_status_marker_html}
                            {thumbnail_html}
                            {audio_button}
                            <label class="ls-track-select-control" title="Select this track">
                                <input type="checkbox" class="track-check" value="{esc(track_id)}"{db_track_checked_attr} aria-label="Select {esc(display_title)}">
                                <span class="ls-track-select-circle" aria-hidden="true">✓</span>
                            </label>
                        </div>
                        <div class="title-stack">
                            <div class="title-line"><a class="title-link" href="{esc(suno_url)}" data-suno-url="{esc(suno_url)}" target="_blank" rel="noopener" title="Atvērt dziesmu Suno.com">{esc(display_title)}</a>{bpm_inline_html}</div>
                            {title_meta_html}
                            {library_secondary_html}
                            {prompt_preview_line_html}
                            {style_under_title_html}
                        </div>
                    </div>
                </td>

                <td class="workspace-cell" data-sort="{esc(lv_sort_key(workspace_text))}">{esc(workspace_text)}</td>

                <td class="created-cell" data-sort="{created_sort}">{esc(created_display)}</td>

                <td class="duration-cell" data-sort="{duration_sort}">{esc(duration_display)}</td>

                <td class="style-cell" data-sort="{esc(lv_sort_key(style_text))}" title="{esc(style_text)}">
                    <div class="style-edit-row">
                        <textarea class="style-edit" data-track-id="{esc(track_id)}" data-original="{esc(style_text)}">{esc(style_text)}</textarea>
                        <div class="style-save-box">
                            <button type="button" class="style-save" data-track-id="{esc(track_id)}" disabled>Save</button>
                            <span class="style-save-status"></span>
                        </div>
                    </div>
                </td>


                <td class="kind-cell" data-sort="{esc(play_type_sort)}">{esc(kind_text)}</td>

                <td class="actions-cell">
                    <div class="audio-actions">
                        {compare_button}
                        <div class="row-menu-wrap">
                            <button
                                type="button"
                                class="row-menu-btn"
                                data-track-id="{esc(track_id)}"
                                data-title="{esc(display_title)}"
                                data-raw-title="{esc(title_clean)}"
                                data-suno-url="{esc(suno_url)}"
                                data-audio-url="{esc(audio_url)}"
                                data-local-wav="{esc(local_wav)}"
                                data-local-mp3="{esc(local_mp3)}"
                                title="More actions"
                            >⋮</button>
                            <div class="row-menu hidden">
                                <button type="button" class="row-menu-item menu-open-suno">Open in Suno</button>
                                <button type="button" class="row-menu-item menu-copy-id">Copy Track ID</button>
                                <button type="button" class="row-menu-item menu-edit-title">Edit LS title...</button>
                                <button type="button" class="row-menu-item menu-edit-lyrics">Edit Lyrics...</button>
                                <button type="button" class="row-menu-item menu-copy-local-path">Kopēt īstā lokālā faila ceļu</button>
                                <button type="button" class="row-menu-item menu-cache-suno-path">Izveidot pagaidu Suno MP3 (edit_cache)</button>
                                <button type="button" class="row-menu-item menu-add-local">Piesaistīt lokālu audio failu...</button>
                                <button type="button" class="row-menu-item menu-add-stem-folder">Add Stem folder</button>
                                <button type="button" class="row-menu-item danger menu-delete-local-variant">Delete local variant</button>
                                <button type="button" class="row-menu-item danger menu-delete-local">Delete local audio (legacy)</button>
                                <button type="button" class="row-menu-item danger menu-hide-track">Hide from Finder</button>
                            </div>
                        </div>
                    </div>
                </td>
            </tr>

            <tr class="fragment-row hidden">
                <td colspan="9">
                    <div class="fragment-player compare-player">
                        <div class="player-block suno-block">
                            <div class="player-title">Suno audio</div>
                            <div class="audio-line">
                                <audio class="audio-player" controls preload="metadata" tabindex="0"></audio>
                                <button
                                    type="button"
                                    class="edit-audio-btn edit-suno-btn"
                                    data-audio-url="{esc(audio_url)}"
                                    data-track-id="{esc(track_id)}"
                                    data-title="{esc(display_title)}"
                                    data-local-path="{esc(local_wav or local_mp3)}"
                                    title="Open linked local audio if available; otherwise create a temporary Suno MP3 in edit_cache"
                                >Edit</button>
                                <button
                                    type="button"
                                    class="loop-audio-btn"
                                    title="Loop: atskaņot šo audio bezgalīgi"
                                >Loop</button>
                            </div>

                            <div class="fragment-controls">
                                <button type="button" class="small-btn back-btn">-10s</button>
                                <button type="button" class="small-btn forward-btn">+10s</button>
                                <button type="button" class="small-btn ab-set-a-btn" title="Ielikt A punktu pašreizējā pozīcijā">Set A</button>
                                <button type="button" class="small-btn ab-set-b-btn" title="Ielikt B punktu pašreizējā pozīcijā">Set B</button>
                                <button type="button" class="small-btn ab-clear-btn" title="Notīrīt A/B cilpu">Clear AB</button>
                                <span class="ab-readout"></span>
                                <span class="zoom-readout"></span>
                                <span class="time-readout">0:00 / 0:00</span>
                                <span class="wave-status">waveform not loaded</span>
                            </div>

                            <div class="waveform-row">
                                <div class="waveform-box" title="Click = seek; Ctrl+wheel = visual zoom; double-click = reset zoom">
                                    <div class="wave-loading">Loading waveform...</div>
                                    <img class="waveform-image" alt="waveform">
                                    <div class="ab-region"></div>
                                    <div class="ab-marker ab-marker-a"><span>A</span></div>
                                    <div class="ab-marker ab-marker-b"><span>B</span></div>
                                    <div class="big-progress-fill"></div>
                                    <div class="big-progress-knob"></div>
                                </div>
                            </div>
                        </div>

                        <div class="player-block local-block hidden">
                            <div class="player-title">Local WAV</div>
                            <div class="audio-line">
                                <audio class="audio-player" controls preload="metadata" tabindex="0"></audio>
                                <button
                                    type="button"
                                    class="edit-audio-btn edit-local-btn"
                                    data-local-path=""
                                    title="Open local WAV in audio editor"
                                >Edit</button>
                                <button
                                    type="button"
                                    class="loop-audio-btn"
                                    title="Loop: atskaņot šo audio bezgalīgi"
                                >Loop</button>
                            </div>

                            <div class="fragment-controls">
                                <button type="button" class="small-btn back-btn">-10s</button>
                                <button type="button" class="small-btn forward-btn">+10s</button>
                                <button type="button" class="small-btn ab-set-a-btn" title="Ielikt A punktu pašreizējā pozīcijā">Set A</button>
                                <button type="button" class="small-btn ab-set-b-btn" title="Ielikt B punktu pašreizējā pozīcijā">Set B</button>
                                <button type="button" class="small-btn ab-clear-btn" title="Notīrīt A/B cilpu">Clear AB</button>
                                <span class="ab-readout"></span>
                                <span class="zoom-readout"></span>
                                <span class="time-readout">0:00 / 0:00</span>
                                <span class="wave-status">waveform not loaded</span>
                            </div>

                            <div class="waveform-row">
                                <div class="waveform-box" title="Click = seek; Ctrl+wheel = visual zoom; double-click = reset zoom">
                                    <div class="wave-loading">Loading waveform...</div>
                                    <img class="waveform-image" alt="waveform">
                                    <div class="ab-region"></div>
                                    <div class="ab-marker ab-marker-a"><span>A</span></div>
                                    <div class="ab-marker ab-marker-b"><span>B</span></div>
                                    <div class="big-progress-fill"></div>
                                    <div class="big-progress-knob"></div>
                                </div>
                            </div>
                        </div>

                        <div class="player-block user-review-block" data-track-id="{esc(track_id)}" data-marks="{user_marks}">
                            <div class="review-tags-box">
                                <button
                                    type="button"
                                    class="small-btn review-tags-open"
                                    data-current-tags="{esc(user_tags)}"
                                    title="Open Flags and Tags panel"
                                >Flags and Tags</button>
                                <div class="review-tags-current" title="LS Flags and Tags">{esc(user_tags)}</div>
                                <span class="review-save-status"></span>
                            </div>
                        </div>
                    </div>
                </td>
            </tr>
        """)

    if not table_rows and include_empty_state:
        table_rows.append("""
            <tr>
                <td colspan="9" class="empty">No active results found.</td>
            </tr>
        """)

    return table_rows

def render_suno_page_shell_controls_style_assets():
    return asset_text('ls_library/static/suno_page_shell_controls_style_assets.css')


def render_suno_page_table_structure_style_assets():
    return asset_text('ls_library/static/suno_page_table_structure_style_assets.css')


def render_suno_page_title_thumbnail_style_assets():
    return asset_text('ls_library/static/suno_page_title_thumbnail_style_assets.css')


def render_suno_page_title_metadata_badges_style_assets():
    return asset_text('ls_library/static/suno_page_title_metadata_badges_style_assets.css')


def render_suno_page_core_table_style_assets():
    """Return core page, controls, Library table and title-row CSS."""
    return (
        render_suno_page_shell_controls_style_assets()
        + render_suno_page_table_structure_style_assets()
        + render_suno_page_title_thumbnail_style_assets()
        + render_suno_page_title_metadata_badges_style_assets()
    )

def render_suno_page_row_metadata_controls_style_assets():
    return asset_text('ls_library/static/suno_page_row_metadata_controls_style_assets.css')


def render_suno_page_audio_controls_style_assets():
    return asset_text('ls_library/static/suno_page_audio_controls_style_assets.css')


def render_suno_page_waveform_navigation_style_assets():
    return asset_text('ls_library/static/suno_page_waveform_navigation_style_assets.css')


def render_suno_page_review_tags_style_assets():
    return asset_text('ls_library/static/suno_page_review_tags_style_assets.css')


def render_suno_page_header_menu_style_assets():
    return asset_text('ls_library/static/suno_page_header_menu_style_assets.css')


def render_suno_page_common_modal_editor_style_assets():
    return asset_text('ls_library/static/suno_page_common_modal_editor_style_assets.css')


def render_suno_page_wav_preview_style_assets():
    return asset_text('ls_library/static/suno_page_wav_preview_style_assets.css')


def render_suno_page_wav_result_style_assets():
    return asset_text('ls_library/static/suno_page_wav_result_style_assets.css')


def render_suno_page_finder_search_style_assets():
    return asset_text('ls_library/static/suno_page_finder_search_style_assets.css')


def render_suno_page_shell_foundation_style_assets():
    return asset_text('ls_library/static/suno_page_shell_foundation_style_assets.css')


def render_suno_page_sidebar_foundation_style_assets():
    return asset_text('ls_library/static/suno_page_sidebar_foundation_style_assets.css')


def render_suno_page_sidebar_profile_style_assets():
    return asset_text('ls_library/static/suno_page_sidebar_profile_style_assets.css')


def render_suno_page_sidebar_navigation_style_assets():
    return asset_text('ls_library/static/suno_page_sidebar_navigation_style_assets.css')


def render_suno_page_sidebar_collapsed_style_assets():
    return asset_text('ls_library/static/suno_page_sidebar_collapsed_style_assets.css')


def render_suno_page_sidebar_style_assets():
    """Return the fixed Suno-style sidebar and navigation CSS."""
    return (
        render_suno_page_sidebar_foundation_style_assets()
        + render_suno_page_sidebar_profile_style_assets()
        + render_suno_page_sidebar_navigation_style_assets()
        + render_suno_page_sidebar_collapsed_style_assets()
    )

def render_suno_page_main_surface_style_assets():
    return asset_text('ls_library/static/suno_page_main_surface_style_assets.css')


def render_suno_page_selected_track_shell_style_assets():
    return asset_text('ls_library/static/suno_page_selected_track_shell_style_assets.css')


def render_suno_page_suno_library_list_style_assets():
    return asset_text('ls_library/static/suno_page_suno_library_list_style_assets.css')


def render_suno_page_visual_shell_style_assets():
    """Return the complete Suno-inspired shell CSS in established order."""
    return "".join((
        render_suno_page_shell_foundation_style_assets(),
        render_suno_page_sidebar_style_assets(),
        render_suno_page_main_surface_style_assets(),
        render_suno_page_selected_track_shell_style_assets(),
        render_suno_page_suno_library_list_style_assets(),
    ))

def render_suno_library_filter_control_style_assets():
    return asset_text('ls_library/static/suno_library_filter_control_style_assets.css')


def render_suno_library_multi_filter_style_assets():
    return asset_text('ls_library/static/suno_library_multi_filter_style_assets.css')


def render_suno_library_sort_control_style_assets():
    return asset_text('ls_library/static/suno_library_sort_control_style_assets.css')


def render_suno_library_tools_menu_style_assets():
    return asset_text('ls_library/static/suno_library_tools_menu_style_assets.css')


def render_suno_page_library_row_style_assets():
    """Return the compact unified Library-row and related responsive CSS."""
    return "".join((
        render_suno_library_filter_control_style_assets(),
        render_suno_library_multi_filter_style_assets(),
        render_suno_library_sort_control_style_assets(),
        render_suno_library_tools_menu_style_assets(),
    ))

def render_suno_filter_tokens_and_chips_style_assets():
    return asset_text('ls_library/static/suno_filter_tokens_and_chips_style_assets.css')


def render_suno_saved_views_filter_style_assets():
    return asset_text('ls_library/static/suno_saved_views_filter_style_assets.css')


def render_suno_filter_overflow_style_assets():
    return asset_text('ls_library/static/suno_filter_overflow_style_assets.css')


def render_localsunodb_search_style_assets():
    return asset_text('ls_library/static/localsunodb_search_style_assets.css')


def render_suno_filter_layout_dock_style_assets():
    return asset_text('ls_library/static/suno_filter_layout_dock_style_assets.css')


def render_suno_page_filter_style_assets():
    """Return the complete Carbon/Whisker filter and viewport-dock CSS."""
    return "".join((
        render_suno_filter_tokens_and_chips_style_assets(),
        render_suno_saved_views_filter_style_assets(),
        render_suno_filter_overflow_style_assets(),
        render_localsunodb_search_style_assets(),
        render_suno_filter_layout_dock_style_assets(),
    ))



