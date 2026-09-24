import base64
import html
import json
import os
import re
import urllib.parse
from pathlib import Path
from ls_core.runtime import *
from ls_core.assets import asset_text, asset_url, render_template_tokens

def render_suno_library_page_document(
    active_search_html,
    category_hidden_inputs,
    category_menu_items,
    category_mode,
    category_mode_controls,
    category_summary,
    clear_all_html,
    finder_search_display_escaped,
    flag_filter_value,
    kind_filter_options_html,
    limit_value,
    local_audio_filter_escaped,
    local_family_hidden_inputs,
    local_family_menu_items,
    local_family_summary,
    pinned_user_tags_initial_json,
    query_escaped,
    refresh_message,
    rows,
    search_lyrics,
    search_lyrics_checked,
    search_marks,
    search_marks_checked,
    search_name,
    search_name_checked,
    search_prompt,
    search_prompt_checked,
    search_tags,
    search_tags_checked,
    selected_track_ids_escaped,
    selection_view_active,
    ls_elza_view_context,
    show_more_html,
    sort_by,
    sort_column_js,
    sort_dir,
    sort_direction_js,
    stats,
    style_query_escaped,
    table_rows,
    tag_filter_value,
    user_tags_initial_json,
    workspace_hidden_inputs,
    workspace_menu_items,
    workspace_mode,
    workspace_mode_controls,
    workspace_summary,
):
    """Render the complete Suno Library HTML document from prepared view state."""
    return render_template_tokens('ls_library/templates/library.html', [
            APP_VERSION,
            render_suno_page_style_block(),
            APP_VERSION,
            esc(get_cached_suno_credits_display()),
            esc(get_cached_suno_credits_display()),
            render_suno_credits_monitor(),
            render_metadata_backfill_alert_monitor('suno'),
            query_escaped,
            style_query_escaped,
            '1' if search_name else '0',
            '1' if search_lyrics else '0',
            '1' if search_prompt else '0',
            '1' if search_marks else '0',
            '1' if search_tags else '0',
            esc(flag_filter_value),
            esc(tag_filter_value),
            selected_track_ids_escaped,
            build_audio_source_filter_options(local_audio_filter_escaped),
            esc(sort_by),
            esc(sort_dir),
            esc(workspace_mode if workspace_mode == 'family_and' else ''),
            esc(category_mode if category_mode == 'family_and' else ''),
            workspace_hidden_inputs,
            category_hidden_inputs,
            local_family_hidden_inputs,
            esc(workspace_summary),
            ''.join(workspace_menu_items),
            workspace_mode_controls,
            esc(local_family_summary),
            ''.join(local_family_menu_items),
            esc(category_summary),
            ''.join(category_menu_items),
            category_mode_controls,
            kind_filter_options_html,
            clear_all_html,
            refresh_message,
            len(rows),
            stats['total_active'],
            stats['total_missing'],
            stats['missing_stems'],
            stats['new_since_last_sync'],
            stats['total_tracks'],
            stats.get('total_main_active', stats['total_active'] - stats['total_stems']),
            stats['total_workspaces'],
            stats['total_with_style'],
            stats['total_liked'],
            stats['total_not_liked'],
            stats['hidden_duplicates'],
            stats.get('total_has_stems', 0),
            stats.get('total_local_stem_files', 0),
            stats['total_stems'],
            stats.get('total_unlinked_stems', 0),
            esc(stats['last_sync_time']),
            stats.get('total_category_song', 0),
            stats.get('total_category_instrumental', 0),
            stats.get('total_category_uncertain', 0),
            stats.get('total_instrumental_review', 0),
            stats.get('total_category_unclassified', 0),
            active_search_html,
            ' selection-mode' if selection_view_active else '',
            ''.join(table_rows),
            show_more_html,
            render_suno_global_player_markup(),
            finder_search_display_escaped,
            search_name_checked,
            search_lyrics_checked,
            search_prompt_checked,
            search_marks_checked,
            search_tags_checked,
            render_suno_panel_layout_script(),
            render_suno_library_lazy_loader_script(),
            render_selected_track_panel_script(),
            render_suno_saved_views_tag_filters_script(user_tags_initial_json, pinned_user_tags_initial_json),
            render_suno_user_tag_catalog_actions_script(),
            render_suno_filter_navigation_script(),
            render_suno_working_overlay_script(),
            render_suno_wav_local_family_script(),
            render_suno_working_overlay_lifecycle_script(),
            render_suno_navigation_work_status_script(),
            render_suno_autoplay_rows_script(sort_column_js, sort_direction_js),
            render_suno_selection_state_script(),
            render_suno_sort_indicator_script(),
            render_suno_view_state_sort_script(),
            render_suno_selection_checkbox_script(),
            render_suno_stems_player_script(),
            render_suno_audio_player_script(),
            render_suno_rating_tags_script(),
            render_suno_inline_style_editor_script(),
            render_suno_selection_restore_open_url_script(),
            render_suno_compare_this_script(),
            render_suno_selection_actions_script(),
            render_suno_edit_row_actions_script(),
            render_suno_keyboard_navigation_script(),
            render_suno_menus_search_settings_script(),
            render_suno_imported_rows_restore_script(),
            render_track_text_editor_script(),
            render_style_modal_close_script(),
            render_ls_update_monitor(),
            render_ls_elza_assets('SUNO Database', ls_elza_view_context, docked=True, local_family_title=get_local_family_title(), app_version=APP_VERSION, opacity=get_ls_elza_background_opacity()),
            render_playlist_library_actions_script() + render_ls_web_runtime_assets() + render_ls_popup_theme_assets()
        ])


def _normalize_library_view_filters(
    workspace,
    workspace_mode,
    category_filter,
    category_mode,
    local_family_filter,
    kind_filter,
):
    selected_workspaces = normalize_multi_filter_values(workspace)
    selected_categories = normalize_multi_filter_values(category_filter)
    selected_local_families = normalize_multi_filter_values(local_family_filter)
    workspace_mode = normalize_family_group_mode(workspace_mode)
    category_mode = normalize_family_group_mode(category_mode)
    if len(selected_workspaces) < 2:
        workspace_mode = "or"
    if len(selected_categories) < 2:
        category_mode = "or"
    if not selected_categories and str(kind_filter or "").strip() in ("Song", "Instrumental"):
        selected_categories = [str(kind_filter).strip()]
        kind_filter = ""
    return (
        selected_workspaces,
        workspace_mode,
        selected_categories,
        category_mode,
        selected_local_families,
        kind_filter,
    )


def _library_family_group_track_ids(
    selected_workspaces,
    workspace_mode,
    selected_categories,
    category_mode,
):
    if workspace_mode != "family_and" and category_mode != "family_and":
        return None
    return get_local_family_group_match_track_ids(
        workspace_values=(
            selected_workspaces if workspace_mode == "family_and" else []
        ),
        category_values=(
            selected_categories if category_mode == "family_and" else []
        ),
    )


def render_library_rows_chunk(
    query="",
    style_query="",
    workspace="",
    workspace_mode="or",
    kind_filter="",
    category_filter="",
    category_mode="or",
    local_family_filter="",
    local_audio_filter="",
    search_name=True,
    search_lyrics=False,
    search_prompt=False,
    search_marks=False,
    search_tags=False,
    flag_filter="",
    tag_filter="",
    track_ids_filter="",
    sort_by="",
    sort_dir="asc",
    cursor="",
    index_start=0,
    batch_size=40,
):
    """Return one cursor-paginated Library HTML chunk without a COUNT query."""
    (
        selected_workspaces,
        workspace_mode,
        selected_categories,
        category_mode,
        selected_local_families,
        kind_filter,
    ) = _normalize_library_view_filters(
        workspace,
        workspace_mode,
        category_filter,
        category_mode,
        local_family_filter,
        kind_filter,
    )

    search_controls = build_finder_search_controls_state(
        query=query,
        style_query=style_query,
        local_audio_filter=local_audio_filter,
        search_name=search_name,
        search_lyrics=search_lyrics,
        search_prompt=search_prompt,
        search_marks=search_marks,
        search_tags=search_tags,
        flag_filter=flag_filter,
        tag_filter=tag_filter,
    )
    local_audio_filter = search_controls["local_audio_filter"]
    search_name = search_controls["search_name"]
    search_lyrics = search_controls["search_lyrics"]
    search_prompt = search_controls["search_prompt"]
    search_marks = search_controls["search_marks"]
    search_tags = search_controls["search_tags"]
    flag_filter_value = search_controls["flag_filter_value"]
    tag_filter_value = search_controls["tag_filter_value"]

    family_group_track_ids = _library_family_group_track_ids(
        selected_workspaces,
        workspace_mode,
        selected_categories,
        category_mode,
    )

    try:
        index_start = max(0, int(index_start or 0))
    except (TypeError, ValueError):
        index_start = 0
    try:
        batch_size = int(batch_size or 40)
    except (TypeError, ValueError):
        batch_size = 40
    batch_size = max(10, min(batch_size, 100))

    sort_by = normalize_sort_by(sort_by)
    if sort_by:
        sort_dir = normalize_sort_dir(sort_dir)
    else:
        sort_by = "created"
        sort_dir = "desc"

    rows_plus_one = search_tracks(
        query=query,
        style_query=style_query,
        workspace=selected_workspaces,
        kind_filter=kind_filter,
        category_filter=selected_categories,
        local_family_filter=selected_local_families,
        local_audio_filter=local_audio_filter,
        limit_value=str(batch_size + 1),
        search_name=search_name,
        search_lyrics=search_lyrics,
        search_prompt=search_prompt,
        search_marks=search_marks,
        search_tags=search_tags,
        flag_filter=flag_filter_value,
        tag_filter=tag_filter_value,
        track_ids_filter=track_ids_filter,
        family_group_track_ids=family_group_track_ids,
        sort_by=sort_by,
        sort_dir=sort_dir,
        cursor_value=cursor,
    )
    has_more = len(rows_plus_one) > batch_size
    rows = rows_plus_one[:batch_size]

    stem_counts = get_stem_counts_for_track_ids([row["id"] for row in rows])
    confirmed_local_audio_paths = get_confirmed_local_audio_paths_for_render(rows)
    local_audio_paths = get_best_local_audio_paths_for_render(
        rows,
        confirmed_paths=confirmed_local_audio_paths,
    )
    selected_track_ids = normalize_track_ids_filter(track_ids_filter)
    selection_view_active = kind_filter == "__last_imported__" or bool(selected_track_ids)
    table_rows = build_library_table_rows(
        rows=rows,
        stem_counts=stem_counts,
        confirmed_local_audio_paths=confirmed_local_audio_paths,
        local_audio_paths=local_audio_paths,
        selection_view_active=selection_view_active,
        kind_filter=kind_filter,
        row_index_start=index_start,
        include_empty_state=False,
    )
    return {
        "ok": True,
        "html": "".join(table_rows),
        "loaded": len(rows),
        "next_cursor": encode_track_page_cursor(rows[-1], sort_by, sort_dir) if rows else "",
        "has_more": bool(has_more),
    }


def render_library_result_count(
    query="",
    style_query="",
    workspace="",
    workspace_mode="or",
    kind_filter="",
    category_filter="",
    category_mode="or",
    local_family_filter="",
    local_audio_filter="",
    search_name=True,
    search_lyrics=False,
    search_prompt=False,
    search_marks=False,
    search_tags=False,
    flag_filter="",
    tag_filter="",
    track_ids_filter="",
):
    """Return the exact current Library result count independently from row loading."""
    (
        selected_workspaces,
        workspace_mode,
        selected_categories,
        category_mode,
        selected_local_families,
        kind_filter,
    ) = _normalize_library_view_filters(
        workspace, workspace_mode, category_filter, category_mode, local_family_filter, kind_filter
    )
    search_controls = build_finder_search_controls_state(
        query=query, style_query=style_query, local_audio_filter=local_audio_filter,
        search_name=search_name, search_lyrics=search_lyrics, search_prompt=search_prompt,
        search_marks=search_marks, search_tags=search_tags, flag_filter=flag_filter, tag_filter=tag_filter,
    )
    family_group_track_ids = _library_family_group_track_ids(
        selected_workspaces, workspace_mode, selected_categories, category_mode
    )
    total = count_tracks(
        query=query,
        style_query=style_query,
        workspace=selected_workspaces,
        kind_filter=kind_filter,
        category_filter=selected_categories,
        local_family_filter=selected_local_families,
        local_audio_filter=search_controls["local_audio_filter"],
        search_name=search_controls["search_name"],
        search_lyrics=search_controls["search_lyrics"],
        search_prompt=search_controls["search_prompt"],
        search_marks=search_controls["search_marks"],
        search_tags=search_controls["search_tags"],
        flag_filter=search_controls["flag_filter_value"],
        tag_filter=search_controls["tag_filter_value"],
        track_ids_filter=track_ids_filter,
        family_group_track_ids=family_group_track_ids,
    )
    return {"ok": True, "total": int(total or 0)}


def render_page(query="", style_query="", workspace="", workspace_mode="or", kind_filter="", category_filter="", category_mode="or", local_family_filter="", like_filter="", local_audio_filter="", limit_value="300", db_refresh="", search_name=True, search_lyrics=False, search_prompt=False, search_marks=False, search_tags=False, flag_filter="", tag_filter="", track_ids_filter="", sort_by="", sort_dir="asc"):
    """Render the Library shell only; rows are loaded incrementally by JavaScript."""
    (
        selected_workspaces,
        workspace_mode,
        selected_categories,
        category_mode,
        selected_local_families,
        kind_filter,
    ) = _normalize_library_view_filters(
        workspace,
        workspace_mode,
        category_filter,
        category_mode,
        local_family_filter,
        kind_filter,
    )

    stats = get_stats()
    sort_by = normalize_sort_by(sort_by)
    if sort_by:
        sort_dir = normalize_sort_dir(sort_dir)
    else:
        sort_by = "created"
        sort_dir = "desc"
    sort_column = {"title": 2, "created": 4, "duration": 5}.get(sort_by)
    sort_column_js = "null" if sort_column is None else str(sort_column)
    sort_direction_js = sort_dir if sort_by else ""
    workspaces = get_workspaces()
    available_user_tags = get_available_user_tags()
    pinned_user_tags = get_pinned_user_tags()
    saved_views = get_saved_views()
    user_tags_initial_json = json.dumps(available_user_tags, ensure_ascii=False).replace("</", "<\\/")
    pinned_user_tags_initial_json = json.dumps(pinned_user_tags, ensure_ascii=False).replace("</", "<\\/")

    family_group_track_ids = _library_family_group_track_ids(
        selected_workspaces,
        workspace_mode,
        selected_categories,
        category_mode,
    )

    selected_track_ids = normalize_track_ids_filter(track_ids_filter)
    selected_track_ids_value = ",".join(selected_track_ids)
    selected_track_ids_escaped = esc(selected_track_ids_value)
    selection_view_active = kind_filter == "__last_imported__" or bool(selected_track_ids)

    search_controls = build_finder_search_controls_state(
        query=query,
        style_query=style_query,
        local_audio_filter=local_audio_filter,
        search_name=search_name,
        search_lyrics=search_lyrics,
        search_prompt=search_prompt,
        search_marks=search_marks,
        search_tags=search_tags,
        flag_filter=flag_filter,
        tag_filter=tag_filter,
    )
    query_escaped = search_controls["query_escaped"]
    style_query_escaped = search_controls["style_query_escaped"]
    local_audio_filter = search_controls["local_audio_filter"]
    local_audio_filter_escaped = search_controls["local_audio_filter_escaped"]
    search_name = search_controls["search_name"]
    search_lyrics = search_controls["search_lyrics"]
    search_prompt = search_controls["search_prompt"]
    search_marks = search_controls["search_marks"]
    search_tags = search_controls["search_tags"]
    selected_flag_filters = search_controls["selected_flag_filters"]
    selected_tag_filters = search_controls["selected_tag_filters"]
    flag_filter_value = search_controls["flag_filter_value"]
    tag_filter_value = search_controls["tag_filter_value"]
    finder_search_display_escaped = search_controls["finder_search_display_escaped"]
    search_name_checked = search_controls["search_name_checked"]
    search_lyrics_checked = search_controls["search_lyrics_checked"]
    search_prompt_checked = search_controls["search_prompt_checked"]
    search_marks_checked = search_controls["search_marks_checked"]
    search_tags_checked = search_controls["search_tags_checked"]

    workspace_family_controls = build_workspace_and_local_family_controls(
        workspaces=workspaces,
        selected_workspaces=selected_workspaces,
        workspace_mode=workspace_mode,
        selected_local_families=selected_local_families,
    )
    workspace_menu_items = workspace_family_controls["workspace_menu_items"]
    workspace_summary = workspace_family_controls["workspace_summary"]
    workspace_mode_controls = workspace_family_controls["workspace_mode_controls"]
    local_family_menu_items = workspace_family_controls["local_family_menu_items"]
    local_family_summary = workspace_family_controls["local_family_summary"]

    category_type_controls = build_category_and_type_controls(
        stats=stats,
        selected_categories=selected_categories,
        category_mode=category_mode,
        kind_filter=kind_filter,
    )
    category_menu_items = category_type_controls["category_menu_items"]
    category_summary = category_type_controls["category_summary"]
    category_mode_controls = category_type_controls["category_mode_controls"]
    kind_filter_options_html = category_type_controls["kind_filter_options_html"]

    filter_form_support = build_filter_form_support_markup(
        selected_workspaces=selected_workspaces,
        selected_categories=selected_categories,
        selected_local_families=selected_local_families,
        db_refresh=db_refresh,
    )
    workspace_hidden_inputs = filter_form_support["workspace_hidden_inputs"]
    category_hidden_inputs = filter_form_support["category_hidden_inputs"]
    local_family_hidden_inputs = filter_form_support["local_family_hidden_inputs"]
    refresh_message = filter_form_support["refresh_message"]

    query_text = str(query or "").strip()
    style_query_text = str(style_query or "").strip()
    active_search_html, clear_all_html, show_more_html = build_filter_navigation_html(
        query=query,
        style_query=style_query,
        query_text=query_text,
        style_query_text=style_query_text,
        selected_workspaces=selected_workspaces,
        workspace_mode=workspace_mode,
        selected_categories=selected_categories,
        category_mode=category_mode,
        selected_local_families=selected_local_families,
        kind_filter=kind_filter,
        local_audio_filter=local_audio_filter,
        limit_value="all",
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
        saved_views=saved_views,
        total_rows=None,
        rows_count=0,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    ls_elza_view_context = build_ls_elza_view_context(
        query_text=query_text,
        style_query_text=style_query_text,
        search_name=search_name,
        search_lyrics=search_lyrics,
        search_prompt=search_prompt,
        search_marks=search_marks,
        search_tags=search_tags,
        selected_workspaces=selected_workspaces,
        workspace_mode=workspace_mode,
        selected_categories=selected_categories,
        category_mode=category_mode,
        selected_local_families=selected_local_families,
        kind_filter=kind_filter,
        total_rows=None,
        loaded_row_count=0,
        limit_value="lazy",
        saved_views=saved_views,
        selected_track_ids=selected_track_ids,
        selection_view_active=selection_view_active,
        local_audio_filter=local_audio_filter,
        family_group_track_ids=family_group_track_ids,
    )

    page = render_suno_library_page_document(
        active_search_html=active_search_html,
        category_hidden_inputs=category_hidden_inputs,
        category_menu_items=category_menu_items,
        category_mode=category_mode,
        category_mode_controls=category_mode_controls,
        category_summary=category_summary,
        clear_all_html=clear_all_html,
        finder_search_display_escaped=finder_search_display_escaped,
        flag_filter_value=flag_filter_value,
        kind_filter_options_html=kind_filter_options_html,
        limit_value="all",
        local_audio_filter_escaped=local_audio_filter_escaped,
        local_family_hidden_inputs=local_family_hidden_inputs,
        local_family_menu_items=local_family_menu_items,
        local_family_summary=local_family_summary,
        pinned_user_tags_initial_json=pinned_user_tags_initial_json,
        query_escaped=query_escaped,
        refresh_message=refresh_message,
        rows=[],
        search_lyrics=search_lyrics,
        search_lyrics_checked=search_lyrics_checked,
        search_marks=search_marks,
        search_marks_checked=search_marks_checked,
        search_name=search_name,
        search_name_checked=search_name_checked,
        search_prompt=search_prompt,
        search_prompt_checked=search_prompt_checked,
        search_tags=search_tags,
        search_tags_checked=search_tags_checked,
        selected_track_ids_escaped=selected_track_ids_escaped,
        selection_view_active=selection_view_active,
        ls_elza_view_context=ls_elza_view_context,
        show_more_html=show_more_html,
        sort_by=sort_by,
        sort_column_js=sort_column_js,
        sort_dir=sort_dir,
        sort_direction_js=sort_direction_js,
        stats=stats,
        style_query_escaped=style_query_escaped,
        table_rows=[],
        tag_filter_value=tag_filter_value,
        user_tags_initial_json=user_tags_initial_json,
        workspace_hidden_inputs=workspace_hidden_inputs,
        workspace_menu_items=workspace_menu_items,
        workspace_mode=workspace_mode,
        workspace_mode_controls=workspace_mode_controls,
        workspace_summary=workspace_summary,
    )
    return page.encode("utf-8")

def render_downloader_page(message=""):
    settings = get_settings()
    local_family_title = get_local_family_title()
    ensure_suno_token_bridge_files()
    token = get_suno_api_token()
    token_invalid_at = str(settings.get("suno_api_token_invalid_at") or "")
    token_updated_at = str(settings.get("suno_api_token_updated_at") or "")
    token_source = str(settings.get("suno_api_token_source") or "")
    bridge_status = get_suno_token_status()
    if token and token_invalid_at:
        token_status = "Sesija beigusies"
    elif token:
        token_status = "Tokens saglabāts"
    else:
        token_status = "Tokens nav saglabāts"
    masked_token = (token[:12] + "..." + token[-8:]) if len(token) > 24 else ("saved" if token else "")
    candidates = get_meta_candidate_rows(80)
    candidate_options = ['<option value="">-- choose missing-metadata track --</option>']
    for item in candidates:
        label = f"{item.get('title') or '[No title]'} — {item.get('workspace') or ''} — {item.get('id') or ''}"[:180]
        candidate_options.append(f'<option value="{esc(item.get("id") or "")}">{esc(label)}</option>')

    page = render_template_tokens('ls_downloader/templates/downloader.html', [
            APP_VERSION,
            render_downloader_page_styles(),
            render_top_tabs('downloader'),
            render_downloader_status_markup(),
            render_downloader_connection_section(token_invalid_at, token, token_status, masked_token, token_updated_at, token_source, bridge_status),
            render_downloader_audio_section(),
            render_downloader_metadata_section(),
            render_downloader_side_panels_markup(),
            render_downloader_section_navigation_script(),
            render_downloader_action_status_script(),
            render_downloader_wav_workflow_script(),
            render_downloader_elza_layout_script(),
            render_downloader_settings_modal_script(),
            render_downloader_working_status_script(),
            render_downloader_metadata_audit_script(),
            render_downloader_state_script(),
            render_downloader_restored_view_script(),
            render_downloader_token_bridge_script(),
            render_downloader_update_workflows_script(),
            render_ls_update_monitor(),
            render_ls_elza_assets('Downloader', docked=True, local_family_title=get_local_family_title(), app_version=APP_VERSION, opacity=get_ls_elza_background_opacity()),
            render_ls_web_runtime_assets() + render_ls_popup_theme_assets()
        ])
    return page.encode("utf-8")
