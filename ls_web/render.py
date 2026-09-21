import base64
import html
import json
import os
import re
import urllib.parse
from pathlib import Path
from ls_core.runtime import *
from ls_core.assets import asset_text, asset_url, render_template_tokens, stylesheet_asset


def render_ls_web_runtime_assets():
    return (
        '<link rel="stylesheet" href="' + asset_url('ls_web/static/common.css') + '">'
        + '<script src="' + asset_url('ls_web/static/event_bus.js') + '"></script>'
        + '<script src="' + asset_url('ls_web/static/changelog_menu.js') + '"></script>'
        + '<script src="' + asset_url('ls_web/static/import_branding.js') + '"></script>'
    )

def render_ls_popup_theme_assets():
    return (
        '<link id="ls-popup-theme-v5113" rel="stylesheet" href="' + asset_url('ls_web/static/popup_theme.css') + '">'
        + '<link id="ls-library-panel-facelift" rel="stylesheet" href="' + asset_url('ls_web/static/library_panel_facelift.css') + '">'
        + '<script src="' + asset_url('ls_web/static/library_panel_facelift.js') + '"></script>'
        + '<link id="ls-library-playback-indicator" rel="stylesheet" href="' + asset_url('ls_web/static/library_playback_indicator.css') + '">'
        + '<script src="' + asset_url('ls_web/static/library_playback_indicator.js') + '"></script>'
    )



def render_suno_credits_monitor():
    return '<script src="' + asset_url('ls_web/static/credits_monitor.js') + '"></script>'



def render_metadata_backfill_alert_monitor(active_section):
    markup = render_template_tokens('ls_web/templates/metadata_backfill_alert.html', [esc(active_section)])
    return markup + '<script src="' + asset_url('ls_web/static/metadata_backfill_alert.js') + '"></script>'



def render_top_tabs(active="suno"):
    def tab_class(key):
        return "header-tab active" if key == active else "header-tab"
    suno_view_url = get_section_view_url("suno")
    downloader_view_url = get_section_view_url("downloader")
    downloader_subnav_html = ""
    if active == "downloader":
        downloader_subnav_html = """
                <div class="ls-sidebar-subnav" aria-label="Importa rīki">
                    <button type="button" class="ls-sidebar-subtab active" data-downloader-section-target="connection" title="Suno savienojums"><span class="ls-sidebar-icon" aria-hidden="true">↔</span><span class="ls-sidebar-label">Savienojums</span></button>
                    <button type="button" class="ls-sidebar-subtab" data-downloader-section-target="audio" title="WAV imports"><span class="ls-sidebar-icon" aria-hidden="true">♪</span><span class="ls-sidebar-label">WAV imports</span></button>
                    <button type="button" class="ls-sidebar-subtab" data-downloader-section-target="metadata" title="Metadati"><span class="ls-sidebar-icon" aria-hidden="true">◎</span><span class="ls-sidebar-label">Metadati</span></button>
                </div>
        """
    values = [
        APP_VERSION,
        esc(get_cached_suno_credits_display()),
        esc(get_cached_suno_credits_display()),
        tab_class('suno'),
        esc(suno_view_url),
        tab_class('downloader'),
        esc(downloader_view_url),
        downloader_subnav_html,
        render_ls_elza_button(),
        esc(suno_view_url),
        render_suno_credits_monitor(),
        render_metadata_backfill_alert_monitor(active)
    ]
    result = render_template_tokens('ls_web/templates/secondary_sidebar.html', values)
    result = result.replace('@@LSCSS@@', '<link rel="stylesheet" href="' + asset_url('ls_web/static/secondary_sidebar.css') + '">')
    result = result.replace('@@LSJS@@', '<script src="' + asset_url('ls_web/static/secondary_sidebar.js') + '"></script>')
    return result



def render_ls_update_monitor():
    return '<script src="' + asset_url('ls_web/static/update_monitor.js') + '"></script>'


def render_suno_page_style_block():
    """Return versioned external stylesheets in the exact v5.394 cascade order."""
    return "".join((
        stylesheet_asset('ls_library/static/suno_page_shell_controls_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_page_table_structure_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_page_title_thumbnail_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_page_title_metadata_badges_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_page_row_metadata_controls_style_assets.css'),
        stylesheet_asset('ls_tools/static/suno_page_row_actions_menu_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_page_audio_controls_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_page_waveform_navigation_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_page_review_tags_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_flags_tags_dock_style.css'),
        stylesheet_asset('ls_stems/static/suno_page_stems_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_page_header_menu_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_page_common_modal_editor_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_page_wav_preview_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_page_wav_result_style_assets.css'),
        stylesheet_asset('ls_tools/static/suno_page_compare_this_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_page_finder_search_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_page_shell_foundation_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_page_sidebar_foundation_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_page_sidebar_profile_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_page_sidebar_navigation_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_page_sidebar_collapsed_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_page_main_surface_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_page_selected_track_shell_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_page_suno_library_list_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_library_filter_control_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_library_multi_filter_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_library_sort_control_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_library_tools_menu_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_filter_tokens_and_chips_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_saved_views_filter_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_filter_overflow_style_assets.css'),
        stylesheet_asset('ls_library/static/localsunodb_search_style_assets.css'),
        stylesheet_asset('ls_library/static/suno_filter_layout_dock_style_assets.css'),
        stylesheet_asset('ls_player/static/suno_global_player_style_assets.css'),
    ))

def render_suno_page_player_waveform_style_assets():
    """Return row editing, actions, audio-player and waveform CSS."""
    return (
        render_suno_page_row_metadata_controls_style_assets()
        + render_suno_page_row_actions_menu_style_assets()
        + render_suno_page_audio_controls_style_assets()
        + render_suno_page_waveform_navigation_style_assets()
    )

def render_suno_page_base_style_assets():
    """Return the complete original Library base CSS in its established order."""
    return "".join((
        render_suno_page_core_table_style_assets(),
        render_suno_page_player_waveform_style_assets(),
        render_suno_page_review_stems_modal_style_assets(),
        render_suno_page_wav_compare_style_assets(),
    ))


def render_suno_page_review_stems_modal_style_assets():
    """Return ratings, tags, stems, header-menu and common modal CSS."""
    return (
        render_suno_page_review_tags_style_assets()
        + render_suno_page_stems_style_assets()
        + render_suno_page_header_menu_style_assets()
        + render_suno_page_common_modal_editor_style_assets()
    )


def render_suno_page_wav_compare_style_assets():
    """Return the complete WAV, Compare This and Finder-search CSS."""
    return (
        render_suno_page_wav_preview_style_assets()
        + render_suno_page_wav_result_style_assets()
        + render_suno_page_compare_this_style_assets()
        + render_suno_page_finder_search_style_assets()
    )
