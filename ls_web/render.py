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
        '<link id="ls-library-panel-facelift" rel="stylesheet" href="' + asset_url('ls_web/static/library_panel_facelift.css') + '">'
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

    nav_html = f"""
                <a class="{tab_class('suno')}" href="{esc(suno_view_url)}" title="Suno Library">
                    <span class="ls-sidebar-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="none">
                            <path d="M7.2 18.2H6a4 4 0 0 1-.6-7.95A6.5 6.5 0 0 1 18 8.2a4.6 4.6 0 0 1-.5 9.18" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                            <path d="M14.5 10.2v7.1a2 2 0 1 1-1.4-1.9v-4.5l4.1-.9v5.9a2 2 0 1 1-1.4-1.9v-4.1l-2.7.6" fill="currentColor"/>
                        </svg>
                    </span>
                    <span class="ls-sidebar-label">Suno Library</span>
                </a>
                <a class="{tab_class('my_library')}" href="/my-library" title="My Library">
                    <span class="ls-sidebar-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="none">
                            <path d="M4 6.5 12 3l8 3.5v11L12 21l-8-3.5v-11Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>
                            <path d="M8 9.5h8M8 13h8M8 16.5h5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
                        </svg>
                    </span>
                    <span class="ls-sidebar-label">My Library</span>
                </a>
                <a class="{tab_class('playlists')}" href="/playlists" title="Playlists">
                    <span class="ls-sidebar-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="none">
                            <path d="M6 6h12M6 12h12M6 18h8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                            <path d="M4 6h.01M4 12h.01M4 18h.01" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"/>
                        </svg>
                    </span>
                    <span class="ls-sidebar-label">Playlists</span>
                </a>
                <button type="button" class="header-tab ls-sidebar-stems-tab"
                        title="Stems ir pieejami Suno Library izvēlētajai dziesmai"
                        aria-label="Stems" disabled>
                    <span class="ls-sidebar-stems-branch" aria-hidden="true"></span>
                    <span class="ls-sidebar-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="none">
                            <path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                        </svg>
                    </span>
                    <span class="ls-sidebar-label">Stems</span>
                </button>
                <a class="{tab_class('downloader')}" href="{esc(downloader_view_url)}" title="Imports">
                    <span class="ls-sidebar-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="none">
                            <path d="M12 3.5v11m0 0 4-4m-4 4-4-4M5 18v2h14v-2" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                        </svg>
                    </span>
                    <span class="ls-sidebar-label">Imports</span>
                </a>
                <a class="header-tab" href="/?ls_action=explore" title="Explore">
                    <span class="ls-sidebar-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="none">
                            <circle cx="10.7" cy="10.7" r="6.2" stroke="currentColor" stroke-width="2"/>
                            <path d="m15.3 15.3 4.4 4.4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                        </svg>
                    </span>
                    <span class="ls-sidebar-label">Explore</span>
                </a>
                <a class="header-tab" href="/?ls_action=elza" title="Open LS Elza">
                    <span class="ls-sidebar-icon ls-sidebar-question-icon" aria-hidden="true">?</span>
                    <span class="ls-sidebar-label">LS Elza</span>
                </a>
                <a class="header-tab" href="/?ls_action=tools" title="Rīki">
                    <span class="ls-sidebar-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="none">
                            <path d="M14.7 6.3a4.2 4.2 0 0 0-5.3 5.3L4 17l3 3 5.4-5.4a4.2 4.2 0 0 0 5.3-5.3l-2.6 2.6-3-3 2.6-2.6Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
                        </svg>
                    </span>
                    <span class="ls-sidebar-label">Rīki</span>
                </a>
    """

    actions_html = """
                <a class="ls-sidebar-bottom-item" href="/?ls_action=auto" title="Auto">
                    <span class="ls-sidebar-icon" aria-hidden="true">▶</span>
                    <span class="ls-sidebar-label">Auto</span>
                </a>
                <a class="ls-sidebar-bottom-item" href="/?ls_action=stats" title="Stats">
                    <span class="ls-sidebar-icon" aria-hidden="true">▥</span>
                    <span class="ls-sidebar-label">Stats</span>
                </a>
                <a class="ls-sidebar-bottom-item" href="/?ls_action=settings" title="Settings">
                    <span class="ls-sidebar-icon" aria-hidden="true">⚙</span>
                    <span class="ls-sidebar-label">Settings</span>
                </a>
                <a class="ls-sidebar-bottom-item" href="/help" title="Help">
                    <span class="ls-sidebar-icon" aria-hidden="true">?</span>
                    <span class="ls-sidebar-label">Help</span>
                </a>
    """

    values = [
        APP_VERSION,
        esc(get_cached_suno_credits_display()),
        esc(get_cached_suno_credits_display()),
        nav_html,
        actions_html,
        render_suno_credits_monitor(),
        render_metadata_backfill_alert_monitor(active),
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
        stylesheet_asset('ls_web/static/popup_theme.css'),
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
