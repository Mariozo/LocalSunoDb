# LS Elza browser UI renderer
# Created: 05.aug.2026   08:00
# Modified: 11.aug.2026   06:30
# Purpose: Render LS Elza HTML, CSS, and JavaScript assets
# Based on: LocalSunoDb Accepted base v5.412
# ver. 1.2 - relax automatic routing and persist local/clarify exchanges

import json


def ls_elza_json_for_script(value):
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def render_ls_elza_button():
    return """
        <button
            type="button"
            class="ls-elza-open-btn"
            id="ls-elza-open-btn"
            title="Open LS Elza"
            aria-label="Open LS Elza"
        >?</button>
    """


def render_ls_elza_shell_controls_style_assets():
    """Return LS Elza launcher, dialog shell, header, and mode-button CSS."""
    return r"""
    <style>
        .ls-elza-open-btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 34px;
            height: 34px;
            padding: 0;
            border: 1px solid rgba(255,255,255,.32);
            border-radius: 50%;
            background: #3c4043;
            color: #fff;
            font-size: 20px;
            font-weight: 800;
            line-height: 1;
        }
        .ls-elza-open-btn:hover {
            background: #4f5968;
            border-color: rgba(255,255,255,.55);
        }
        .ls-elza-modal {
            position: fixed;
            inset: 0;
            z-index: 5000;
            display: none;
            pointer-events: none;
            background: transparent;
        }
        .ls-elza-dialog {
            --ls-elza-opacity: .50;
            position: absolute;
            top: 72px;
            right: 18px;
            display: flex;
            flex-direction: column;
            width: min(410px, calc(100vw - 24px));
            height: min(700px, calc(100vh - 24px));
            overflow: hidden;
            pointer-events: auto;
            border: 1px solid rgba(130,142,158,.86);
            border-radius: 14px;
            background: transparent;
            color: #202124;
            box-shadow: 0 18px 54px rgba(0,0,0,.34);
            backdrop-filter: blur(3px);
        }
        .ls-elza-head {
            display: flex;
            align-items: center;
            gap: 9px;
            padding: 10px 11px;
            border-bottom: 1px solid #d4dae2;
            background: #202124;
            color: #fff;
            cursor: move;
            user-select: none;
            touch-action: none;
        }
        .ls-elza-head button,
        .ls-elza-head input {
            cursor: pointer;
            user-select: auto;
            touch-action: auto;
        }
        .ls-elza-title-box {
            min-width: 0;
            flex: 1 1 auto;
        }
        .ls-elza-title {
            font-size: 17px;
            font-weight: 800;
        }
        .ls-elza-context-line {
            margin-top: 2px;
            overflow: hidden;
            color: #bdc6d3;
            font-size: 12px;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .ls-elza-head-actions {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .ls-elza-head button {
            min-height: 30px;
            padding: 5px 8px;
            border: 1px solid #626b78;
            border-radius: 8px;
            background: #34383f;
            color: #fff;
            font-size: 12px;
            font-weight: 700;
        }
        .ls-elza-head button:hover:not(:disabled) { background: #48505b; }
        .ls-elza-head .ls-elza-icon-btn,
        .ls-elza-head .ls-elza-close {
            width: 31px;
            padding: 0;
            font-size: 18px;
        }
        .ls-elza-mode-btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 34px;
            height: 30px;
            padding: 3px;
            border: 1px solid #5c6877;
            border-radius: 8px;
            background: #303844;
            cursor: pointer;
            transition: background .14s ease, border-color .14s ease, box-shadow .14s ease;
        }
        .ls-elza-mode-btn img {
            display: block;
            width: 22px;
            height: 22px;
            pointer-events: none;
            filter: brightness(0) invert(1);
        }
        .ls-elza-mode-btn:disabled,
        .ls-elza-mode-btn:disabled:hover,
        .ls-elza-mode-btn:disabled:focus {
            border-color: #5c6877;
            background: #303844;
            box-shadow: none;
            color: #fff;
            cursor: default;
            opacity: 1;
        }
        .ls-elza-mode-btn:disabled img {
            filter: brightness(0) invert(1);
        }
        .ls-elza-mode-btn.active,
        .ls-elza-mode-btn[aria-pressed="true"] {
            border-color: #9fd4b5;
            background: #b9dec8;
            box-shadow: 0 0 0 2px rgba(185,222,200,.22);
        }
        .ls-elza-mode-btn.active:hover,
        .ls-elza-mode-btn[aria-pressed="true"]:hover {
            background: #c9e7d5;
        }
        .ls-elza-mode-btn.active img,
        .ls-elza-mode-btn[aria-pressed="true"] img {
            filter: none;
        }"""

def render_ls_elza_settings_history_style_assets():
    """Return LS Elza settings, history, and empty-state CSS."""
    return r"""
        .ls-elza-settings-panel {
            display: none;
            padding: 10px 12px;
            border-bottom: 1px solid rgba(170,180,193,.82);
            background: rgba(247,249,252,.96);
            color: #202124;
            box-shadow: 0 8px 22px rgba(0,0,0,.12);
        }
        .ls-elza-settings-panel.open { display: block; }
        .ls-elza-settings-row {
            display: grid;
            grid-template-columns: auto minmax(100px,1fr) 48px;
            gap: 9px;
            align-items: center;
            font-size: 12px;
            font-weight: 700;
        }
        .ls-elza-settings-row input[type="range"] { width: 100%; }
        .ls-elza-opacity-value {
            text-align: right;
            font-family: Consolas, "Courier New", monospace;
        }
        .ls-elza-settings-status {
            min-height: 15px;
            margin-top: 4px;
            color: #667085;
            font-size: 11px;
        }
        .ls-elza-history {
            flex: 1 1 auto;
            overflow-y: auto;
            padding: 13px;
            background: rgb(238 242 247 / var(--ls-elza-opacity));
        }
        .ls-elza-empty {
            max-width: 520px;
            margin: 36px auto;
            color: #687386;
            text-align: center;
            line-height: 1.5;
        }"""

def render_ls_elza_message_markdown_style_assets():
    """Return LS Elza message, copy-action, and Markdown-content CSS."""
    return r"""
        .ls-elza-message {
            width: 100%;
            max-width: 100%;
            box-sizing: border-box;
            margin: 0 0 11px;
        }
        .ls-elza-message-user,
        .ls-elza-message-assistant {
            margin-left: 0;
            margin-right: 0;
        }
        .ls-elza-message-role {
            display: inline;
            margin-right: 5px;
            color: inherit;
            font-size: inherit;
            font-weight: 800;
            line-height: inherit;
        }
        .ls-elza-copy-btn {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 28px;
            height: 28px;
            min-width: 28px;
            min-height: 28px;
            padding: 0;
            border: 0;
            border-radius: 6px;
            background: transparent;
            color: #7a8390;
            cursor: pointer;
            line-height: 1;
            margin: 0;
        }
        .ls-elza-copy-btn:hover {
            background: rgba(73,84,99,.09);
            color: #3f4a59;
        }
        .ls-elza-copy-btn:focus-visible {
            outline: 2px solid #7ba7dc;
            outline-offset: 1px;
        }
        .ls-elza-copy-btn svg {
            display: block;
            width: 17px;
            height: 17px;
            pointer-events: none;
        }
        .ls-elza-copy-btn.copied {
            background: rgba(62,138,83,.10);
            color: #24633a;
        }
        .ls-elza-copy-btn.copy-failed {
            background: rgba(179,38,30,.08);
            color: #a9322a;
        }
        .ls-elza-bubble {
            width: 100%;
            box-sizing: border-box;
            padding: 5px 5px 4px;
            border: 0;
            border-radius: 0;
            background: transparent;
            box-shadow: none;
            font-size: 14px;
            line-height: 1.48;
            overflow-wrap: anywhere;
        }
        .ls-elza-bubble p { margin: 0 0 9px; }
        .ls-elza-bubble p:last-child { margin-bottom: 0; }
        .ls-elza-view-actions {
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 7px;
            margin-top: 11px;
        }
        .ls-elza-view-action {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-height: 34px;
            margin: 0;
            padding: 6px 12px;
            border: 1px solid #0b57d0;
            border-radius: 9px;
            background: #0b57d0;
            color: #fff;
            font: 700 12px/1.2 "Segoe UI", Arial, sans-serif;
            cursor: pointer;
        }
        .ls-elza-view-action:hover { background: #0847ad; }
        .ls-elza-view-action-secondary {
            border-color: #8b9891;
            background: #fff;
            color: #27312c;
        }
        .ls-elza-view-action-secondary:hover {
            border-color: #5e6b65;
            background: #eef3f0;
            color: #17201c;
        }
        .ls-elza-view-action-secondary:disabled,
        .ls-elza-view-action-secondary:disabled:hover {
            border-color: #a8b1ac;
            background: #eef3f0;
            color: #52605a;
            cursor: default;
            opacity: .82;
        }
        .ls-elza-bubble ul,
        .ls-elza-bubble ol {
            margin: 5px 0 10px;
            padding-left: 24px;
        }
        .ls-elza-bubble li { margin: 3px 0; }
        .ls-elza-bubble strong { font-weight: 800; }
        .ls-elza-bubble code {
            padding: 1px 5px;
            border: 1px solid #d4dae2;
            border-radius: 5px;
            background: #eef2f7;
            font-family: Consolas, "Courier New", monospace;
            font-size: .93em;
        }
        .ls-elza-bubble pre {
            overflow-x: auto;
            margin: 7px 0 10px;
            padding: 10px 11px;
            border-radius: 8px;
            background: #20252d;
            color: #f1f3f4;
            white-space: pre-wrap;
        }
        .ls-elza-bubble pre code {
            padding: 0;
            border: 0;
            background: transparent;
            color: inherit;
        }
        .ls-elza-bubble blockquote {
            margin: 7px 0 10px;
            padding: 6px 10px;
            border-left: 4px solid #7ba7dc;
            background: rgba(123,167,220,.10);
            color: #445064;
        }
        .ls-elza-markdown-heading {
            margin: 6px 0 7px;
            font-size: 1.08em;
            font-weight: 850;
        }
        .ls-elza-message-user .ls-elza-bubble {
            width: fit-content;
            max-width: 88%;
            margin-left: auto;
            padding: 10px 12px 5px;
            border: 1px solid #90b7ea;
            border-radius: 13px;
            background: #dcecff;
            box-shadow: 0 2px 7px rgba(32,44,62,.07);
        }
        .ls-elza-message-footer {
            display: flex;
            align-items: center;
            justify-content: flex-end;
            gap: 5px;
            min-height: 28px;
            margin-top: 6px;
        }
        .ls-elza-message-time {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            height: 28px;
            min-height: 28px;
            box-sizing: border-box;
            color: #7a8390;
            font-size: 16px;
            font-weight: 700;
            line-height: 17px;
            margin: 0;
            opacity: .82;
            white-space: nowrap;
        }
        .ls-elza-message-user .ls-elza-message-time { color: #55718f; }
        .ls-elza-message-footer .ls-elza-copy-btn {
            margin: 0;
        }"""

def render_ls_elza_dock_style_assets():
    """Return LS Elza docking, placeholder, and docked-dialog CSS."""
    return r"""
        .ls-elza-dock-slot {
            margin-top: 16px;
            transition: transform .12s ease, opacity .12s ease;
        }
        .ls-elza-dock-slot[data-dock-position="top"] {
            margin-top: 0;
            margin-bottom: 16px;
        }
        .ls-elza-dock-slot.ls-elza-dock-empty {
            display: none;
        }
        .ls-elza-dock-slot.ls-elza-dock-dragging {
            opacity: .96;
            transition: none;
        }
        .ls-elza-dock-placeholder {
            position: relative;
            width: 100%;
            min-height: 94px;
            box-sizing: border-box;
            margin: 0 0 16px;
            border: 3px dashed rgba(58, 180, 105, .82);
            border-radius: 14px;
            background: rgba(58, 180, 105, .13);
        }
        .ls-elza-dock-placeholder::after {
            content: "Drop LS Elza here";
            position: absolute;
            inset: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #d8ffe5;
            font-size: 14px;
            font-weight: 800;
            letter-spacing: .2px;
            text-shadow: 0 1px 2px rgba(0,0,0,.65);
        }
        .ls-elza-dock-placeholder[data-dock-target="bottom"] {
            margin: 16px 0 0;
            border-color: rgba(98, 151, 220, .84);
            background: rgba(98, 151, 220, .14);
        }
        .ls-elza-dock-slot.ls-elza-dock-target-top .ls-elza-dialog {
            outline: 3px solid rgba(58, 180, 105, .78);
            outline-offset: -3px;
        }
        .ls-elza-dock-slot.ls-elza-dock-target-bottom .ls-elza-dialog {
            outline: 3px solid rgba(98, 151, 220, .78);
            outline-offset: -3px;
        }
        .ls-elza-dock-grip {
            display: none;
            flex: 0 0 auto;
            color: #aeb8c5;
            font-size: 18px;
            font-weight: 900;
            letter-spacing: -4px;
            line-height: 1;
        }
        .ls-elza-modal.ls-elza-docked {
            position: static;
            inset: auto;
            z-index: auto;
            display: block;
            width: 100%;
            pointer-events: auto;
        }
        .ls-elza-modal.ls-elza-docked .ls-elza-dialog {
            position: static;
            inset: auto;
            width: 100%;
            height: 620px;
            max-height: 78vh;
            border-color: rgba(255,255,255,.14);
            border-radius: 14px;
            box-shadow: none;
            backdrop-filter: none;
        }
        .ls-elza-modal.ls-elza-docked .ls-elza-head {
            cursor: grab;
            touch-action: none;
        }
        .ls-elza-modal.ls-elza-docked .ls-elza-head:active {
            cursor: grabbing;
        }
        .ls-elza-modal.ls-elza-docked .ls-elza-dock-grip { display: inline-block; }
        .ls-elza-modal.ls-elza-docked .ls-elza-title { font-size: 15px; }
        .ls-elza-modal.ls-elza-docked .ls-elza-context-line { max-width: 205px; }
        .ls-elza-modal.ls-elza-docked .ls-elza-head-actions { gap: 3px; }
        .ls-elza-modal.ls-elza-docked .ls-elza-head button {
            padding: 4px 6px;
            font-size: 11px;
        }
        .ls-elza-modal.ls-elza-docked .ls-elza-send {
            min-height: 34px;
        }"""

def render_ls_elza_compose_mobile_style_assets():
    """Return LS Elza composer, attachments, input, send, and mobile CSS."""
    return r"""
        .ls-elza-compose {
            padding: 10px 11px 11px;
            border-top: 1px solid rgba(180,190,202,.88);
            background: rgb(247 249 252 / var(--ls-elza-opacity));
        }
        .ls-elza-status {
            min-height: 18px;
            margin-bottom: 6px;
            color: #657184;
            font-size: 12px;
        }
        .ls-elza-status.error { color: #b3261e; font-weight: 700; }
        .ls-elza-status.ls-elza-thinking {
            display: flex;
            align-items: center;
            min-height: 18px;
        }
        .ls-elza-thinking-dots {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            height: 14px;
        }
        .ls-elza-thinking-dot {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: currentColor;
            opacity: .34;
            transform: translateY(0) scale(.82);
            animation: ls-elza-thinking-pulse 920ms ease-in-out infinite;
        }
        .ls-elza-thinking-dot:nth-child(2) { animation-delay: 150ms; }
        .ls-elza-thinking-dot:nth-child(3) { animation-delay: 300ms; }
        @keyframes ls-elza-thinking-pulse {
            0%, 60%, 100% {
                opacity: .34;
                transform: translateY(0) scale(.82);
            }
            30% {
                opacity: 1;
                transform: translateY(-2px) scale(1);
            }
        }
        @media (prefers-reduced-motion: reduce) {
            .ls-elza-thinking-dot {
                animation: none;
                opacity: .72;
                transform: none;
            }
        }
        .ls-elza-attachments {
            display: none;
            gap: 7px;
            overflow-x: auto;
            margin: 0 0 8px;
            padding: 2px 1px 4px;
        }
        .ls-elza-attachments.has-items { display: flex; }
        .ls-elza-attachment {
            position: relative;
            flex: 0 0 68px;
            width: 68px;
            padding: 4px;
            border: 1px solid #c8d0db;
            border-radius: 9px;
            background: rgba(255,255,255,.94);
            box-shadow: 0 1px 4px rgba(32,44,62,.08);
        }
        .ls-elza-attachment img {
            display: block;
            width: 58px;
            height: 48px;
            border-radius: 6px;
            object-fit: cover;
            background: #eef2f7;
        }
        .ls-elza-attachment-name {
            overflow: hidden;
            margin-top: 3px;
            color: #596474;
            font-size: 9px;
            line-height: 1.2;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .ls-elza-attachment-remove {
            position: absolute;
            top: -5px;
            right: -5px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 19px;
            height: 19px;
            padding: 0;
            border: 1px solid #aeb7c3;
            border-radius: 50%;
            background: #fff;
            color: #4b5563;
            font-size: 14px;
            font-weight: 800;
            line-height: 1;
            cursor: pointer;
        }
        .ls-elza-dialog.image-dragover {
            outline: 3px solid rgba(11,87,208,.48);
            outline-offset: -4px;
        }
        .ls-elza-input-row {
            display: block;
        }
        .ls-elza-input {
            width: 100%;
            min-height: 72px;
            max-height: 180px;
            box-sizing: border-box;
            resize: vertical;
            padding: 10px 11px;
            border: 1px solid #aeb8c5;
            border-radius: 10px;
            background: #fff;
            color: #202124;
            font: 14px/1.4 "Segoe UI", Arial, sans-serif;
        }
        .ls-elza-input.ls-elza-input-clarified {
            background: #5BB7D1;
            color: #000;
        }
        .ls-elza-send {
            min-width: 88px;
            min-height: 34px;
            border: 1px solid #1658a8;
            border-radius: 10px;
            background: #0b57d0;
            color: #fff;
            font-weight: 800;
        }
        .ls-elza-send:hover { background: #0847ad; }
        .ls-elza-send:disabled,
        .ls-elza-head button:disabled {
            cursor: default;
            opacity: .55;
        }
        .ls-elza-hint {
            margin-top: 6px;
            color: #7b8492;
            font-size: 11px;
        }
        .ls-elza-mode-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 6px;
            margin-top: 7px;
            min-height: 34px;
        }
        @media (max-width: 650px) {
            .ls-elza-dialog {
                width: calc(100vw - 12px);
                height: calc(100vh - 12px);
            }
            .ls-elza-head { gap: 5px; }
            .ls-elza-title { font-size: 15px; }
            .ls-elza-context-line { max-width: 130px; }
            .ls-elza-head button { padding: 4px 6px; }
            .ls-elza-message { max-width: 100%; }
        }
    </style>
"""

def render_ls_elza_style_assets():
    """Return the complete LS Elza CSS in its original order."""
    return "".join((
        render_ls_elza_shell_controls_style_assets(),
        render_ls_elza_settings_history_style_assets(),
        render_ls_elza_message_markdown_style_assets(),
        render_ls_elza_dock_style_assets(),
        render_ls_elza_compose_mobile_style_assets(),
    ))


def render_ls_elza_dialog_markup():
    """Return the static LS Elza dialog markup unchanged."""
    return r"""
    <div class="ls-elza-modal" id="ls-elza-modal" aria-hidden="true">
        <section class="ls-elza-dialog" id="ls-elza-dialog" role="dialog" aria-modal="false" aria-labelledby="ls-elza-title">
            <div class="ls-elza-head" id="ls-elza-drag-handle" title="Drag LS Elza">
                <span class="ls-elza-dock-grip" aria-hidden="true">⠿</span>
                <div class="ls-elza-title-box">
                    <div class="ls-elza-title" id="ls-elza-title">Elza v2.25</div>
                    <div class="ls-elza-context-line" id="ls-elza-context-line"></div>
                </div>
                <div class="ls-elza-head-actions">
                    <button type="button" id="ls-elza-new-chat">New chat</button>
                    <button type="button" id="ls-elza-clear">Clear</button>
                    <button type="button" class="ls-elza-icon-btn" id="ls-elza-dock-toggle" title="Dock LS Elza" aria-label="Dock LS Elza" aria-pressed="false">⇲</button>
                    <button type="button" class="ls-elza-icon-btn" id="ls-elza-settings-toggle" title="LS Elza settings" aria-label="LS Elza settings">⚙</button>
                    <button type="button" class="ls-elza-close" id="ls-elza-close" aria-label="Close">×</button>
                </div>
            </div>
            <div class="ls-elza-settings-panel" id="ls-elza-settings-panel">
                <label class="ls-elza-settings-row" for="ls-elza-opacity">
                    <span>Background opacity</span>
                    <input type="range" id="ls-elza-opacity" min="20" max="100" step="5" value="__LS_ELZA_OPACITY_VALUE__">
                    <span class="ls-elza-opacity-value" id="ls-elza-opacity-value">__LS_ELZA_OPACITY_VALUE__%</span>
                </label>
                <div class="ls-elza-settings-status" id="ls-elza-settings-status"></div>
            </div>
            <div class="ls-elza-history" id="ls-elza-history"></div>
            <div class="ls-elza-compose">
                <div class="ls-elza-status" id="ls-elza-status"></div>
                <div class="ls-elza-attachments" id="ls-elza-attachments"></div>
                <div class="ls-elza-input-row">
                    <textarea class="ls-elza-input" id="ls-elza-input" placeholder="Ask LS Elza about LocalSunoDb..."></textarea>
                </div>
                <div class="ls-elza-mode-row" aria-label="LS Elza modes">
                    <button
                        type="button"
                        class="ls-elza-mode-btn"
                        id="ls-elza-ux-mode"
                        data-ls-elza-mode="UX_REVIEW"
                        title="Use UX review mode"
                        aria-label="Use UX review mode"
                        aria-pressed="false"
                    >UX</button>
                    <button
                        type="button"
                        class="ls-elza-mode-btn"
                        id="ls-elza-test-mode"
                        data-ls-elza-mode="TEST_REVIEW"
                        title="Use function test mode"
                        aria-label="Use function test mode"
                        aria-pressed="false"
                    >Test</button>
                    <button
                        type="button"
                        class="ls-elza-mode-btn"
                        id="ls-elza-track-mode"
                        data-ls-elza-mode="TRACK_DB"
                        title="Select one track to use Track analysis mode"
                        aria-label="Select one track to use Track analysis mode"
                        aria-pressed="false"
                        disabled
                    >Track</button>
                    <button
                        type="button"
                        class="ls-elza-mode-btn"
                        id="ls-elza-code-mode"
                        data-ls-elza-mode="LS_CODE"
                        title="Analyze the currently running LocalSunoDb source"
                        aria-label="Use read-only code analysis mode"
                        aria-pressed="false"
                    >Code</button>
                    <button type="button" class="ls-elza-send" id="ls-elza-send">Ask</button>
                </div>
                <div class="ls-elza-hint">Enter = send · Shift+Enter = new line · Ctrl+V / drop image · consultation-only</div>
            </div>
        </section>
    </div>
"""


def render_ls_elza_script_state_bootstrap_assets():
    """Return LS Elza setup, element references, mode, and draft state."""
    return r"""
    <script>
    (() => {
        const configuredActiveTab = __LS_ELZA_ACTIVE_TAB_JSON__;
        const serverLocalFamilyTitle = __LS_ELZA_LOCAL_FAMILY_JSON__;
        const appVersion = __LS_ELZA_APP_VERSION_JSON__;
        const serverViewContext = __LS_ELZA_VIEW_CONTEXT_JSON__;
        const serverBackgroundOpacity = __LS_ELZA_OPACITY_JSON__;
        const dockAvailable = __LS_ELZA_DOCKED_JSON__;
        const chatStorageKey = "ls_elza_current_chat_v1";
        const windowStateStorageKey = "ls_elza_window_state_v1";
        const draftStorageKey = "ls_elza_unsent_draft_v1";
        const selectedModeStorageKey = "ls_elza_selected_mode_v1";
        const allowedSelectedModes = new Set([
            "", "UX_REVIEW", "TEST_REVIEW", "TRACK_DB", "LS_CODE"
        ]);
        const maxImagesPerMessage = 4;
        const maxImageBytes = 5 * 1024 * 1024;
        const maxTotalImageBytes = 12 * 1024 * 1024;
        const allowedImageTypes = new Set([
            "image/png", "image/jpeg", "image/webp"
        ]);
        let pendingLsElzaSaveViewButton = null;

        const openButton = document.getElementById("ls-elza-open-btn");
        const modal = document.getElementById("ls-elza-modal");
        const dialog = document.getElementById("ls-elza-dialog");
        const dragHandle = document.getElementById("ls-elza-drag-handle");
        const closeButton = document.getElementById("ls-elza-close");
        const newChatButton = document.getElementById("ls-elza-new-chat");
        const clearButton = document.getElementById("ls-elza-clear");
        const historyBox = document.getElementById("ls-elza-history");
        const input = document.getElementById("ls-elza-input");
        const sendButton = document.getElementById("ls-elza-send");
        const statusLine = document.getElementById("ls-elza-status");
        const contextLine = document.getElementById("ls-elza-context-line");
        const dockToggleButton = document.getElementById("ls-elza-dock-toggle");
        const settingsToggle = document.getElementById("ls-elza-settings-toggle");
        const settingsPanel = document.getElementById("ls-elza-settings-panel");
        const opacitySlider = document.getElementById("ls-elza-opacity");
        const opacityValue = document.getElementById("ls-elza-opacity-value");
        const settingsStatus = document.getElementById("ls-elza-settings-status");
        const attachmentsBox = document.getElementById("ls-elza-attachments");
        const dockSlot = document.getElementById("ls-elza-dock-slot");
        const modeButtons = Array.from(
            document.querySelectorAll("[data-ls-elza-mode]")
        );

        if (!openButton || !modal || !dialog || !historyBox || !input || !sendButton) {
            return;
        }

        let chatId = "";
        let isDocked = false;
        let requestActive = false;
        let chatLoaded = false;
        let dragState = null;
        let imageDragDepth = 0;
        let pendingImages = [];
        let selectedMode = "";
        let clarifiedDraftActive = false;
        let uxCaptureStream = null;
        try {
            chatId = localStorage.getItem(chatStorageKey) || "";
        } catch (error) {}

        try {
            const storedMode = String(
                localStorage.getItem(selectedModeStorageKey) || ""
            ).toUpperCase();
            selectedMode = allowedSelectedModes.has(storedMode)
                ? storedMode
                : "";
        } catch (error) {}

        function refreshModeButtons() {
            const hasSingleSelectedTrack =
                collectContext().selected_track_ids.length === 1;
            modeButtons.forEach((button) => {
                const buttonMode = String(
                    button.dataset.lsElzaMode || ""
                ).toUpperCase();
                const isActive = Boolean(buttonMode && buttonMode === selectedMode);
                button.classList.toggle("active", isActive);
                button.setAttribute("aria-pressed", isActive ? "true" : "false");
                if (buttonMode === "UX_REVIEW") {
                    const label = isActive
                        ? "UX review mode is active. Click to use automatic mode."
                        : "Use UX review mode";
                    button.title = label;
                    button.setAttribute("aria-label", label);
                } else if (buttonMode === "TEST_REVIEW") {
                    const label = isActive
                        ? "Function test mode is active. Click to use automatic mode."
                        : "Use function test mode";
                    button.title = label;
                    button.setAttribute("aria-label", label);
                } else if (buttonMode === "TRACK_DB") {
                    button.disabled = !hasSingleSelectedTrack && !isActive;
                    const label = isActive && !hasSingleSelectedTrack
                        ? "Track analysis mode is active. Select one track if its data is needed."
                        : !hasSingleSelectedTrack
                        ? "Select one track to use Track analysis mode"
                        : isActive
                            ? "Track analysis mode is active. Click to use automatic mode."
                            : "Analyze the selected track";
                    button.title = label;
                    button.setAttribute("aria-label", label);
                } else if (buttonMode === "LS_CODE") {
                    const label = isActive
                        ? "Read-only code analysis mode is active. Click to use automatic mode."
                        : "Analyze the currently running LocalSunoDb source";
                    button.title = label;
                    button.setAttribute("aria-label", label);
                }
            });
            input.placeholder = selectedMode === "TRACK_DB"
                ? "Ask LS Elza about the selected Audio Track..."
                : selectedMode === "LS_CODE"
                    ? "Ask LS Elza about the current LocalSunoDb code..."
                    : "Ask LS Elza about LocalSunoDb...";
        }

        function setSelectedMode(value) {
            const normalized = String(value || "").toUpperCase();
            selectedMode = allowedSelectedModes.has(normalized)
                ? normalized
                : "";
            try {
                if (selectedMode) {
                    localStorage.setItem(selectedModeStorageKey, selectedMode);
                } else {
                    localStorage.removeItem(selectedModeStorageKey);
                }
            } catch (error) {}
            refreshModeButtons();
        }

        refreshModeButtons();

        function assessLsElzaQuestion(message, context) {
            const source = String(message || "").trim();
            const text = source
                .toLocaleLowerCase()
                .normalize("NFD")
                .replace(/[\u0300-\u036f]/g, "");
            const simpleAcknowledgement = /^\s*(?:ok|labi|skaidrs|saprotu|paldies|thanks|thank\s+you|great|super|jā|ja)[\s.!?👍👌😊🙂]*$/i.test(text);
            if (simpleAcknowledgement) {
                return {mode: "", ambiguous: false};
            }
            const explicitCodeRequest = (
                /\b(koda|kodu|source\s+code|programmas\s+avot|funkcijas\s+definic|implementacij)\b/i.test(text)
                && /\b(atrod|mekle|analize|parbaudi|izlasi|paradi|kapec|why|find|inspect|analy[sz]e|read)\b/i.test(text)
            );
            if (explicitCodeRequest) {
                return {mode: "LS_CODE", ambiguous: false};
            }

            const faultRequest = /\b(nedarbo\w*|nerea\w*|nenotiek\w*|neizpild\w*|klud\w*|bug|fail|nepareiz\w*|pazud\w*|nav\s+redzam\w*|saluz\w*|regres\w*|iesprud\w*|unexpected|broken|doesn'?t\s+work|not\s+working|error)\b/i.test(text);
            if (faultRequest) {
                return {mode: "TEST_REVIEW", ambiguous: false};
            }

            const selectedTrackQuestion = /\b(sai\s+dziesm\w*|sis\s+dziesm\w*|izvelet\w*\s+dziesm\w*|izvelet\w*\s+track|this\s+(?:song|track)|selected\s+(?:song|track)|track\s*id|wav|stems?|lokal\w*\s+audio|local\s+(?:audio|wav|family)|kategorij\w*|workspace)\b/i.test(text);
            if (selectedTrackQuestion) {
                return {mode: "TRACK_DB", ambiguous: false};
            }

            const uiHelpQuestion = /\b(poga|panel\w*|ciln\w*|filtr\w*|karodz\w*|flags?|zvaigzn\w*|downloader|compare|select\s+wav|refresh|update|reset|clear|iestat\w*|settings|ka\s+lietot|kur\s+(?:ir|atrodas)|ko\s+(?:dara|nozime))\b/i.test(text);
            if (uiHelpQuestion) {
                return {mode: "UX_REVIEW", ambiguous: false};
            }

            const generalQuestion = /\b(suno(?:\.com|\s+ai|\s+studio)?|openai|audacity|windows|muzik\w*|dziesm\w*\s+stil\w*)\b/i.test(text);
            if (generalQuestion) {
                return {mode: "UX_REVIEW", ambiguous: false};
            }

            // A selected track is context, not permission to force every unrelated
            // question into TRACK_DB. Unknown but complete questions go to the
            // normal LS Elza route; only explicit ambiguity checks should clarify.
            return {mode: "", ambiguous: false};
        }

        function chooseLsElzaModeForQuestion(message, context) {
            return assessLsElzaQuestion(message, context).mode;
        }

        function clearClarifiedDraftState() {
            clarifiedDraftActive = false;
            input.classList.toggle("ls-elza-input-clarified", false);
        }

        function setClarifiedDraft(value) {
            input.value = String(value || "");
            clarifiedDraftActive = Boolean(input.value);
            input.classList.toggle(
                "ls-elza-input-clarified",
                clarifiedDraftActive
            );
            saveUnsentDraft(input.value);
            setStatus("");
            input.focus();
            input.select();
        }

        function needsLsElzaVisualContext(message, mode) {
            const normalizedMode = String(mode || "").toUpperCase();
            if (normalizedMode !== "UX_REVIEW" && normalizedMode !== "TEST_REVIEW") {
                return false;
            }
            const text = String(message || "")
                .toLocaleLowerCase()
                .normalize("NFD")
                .replace(/[\u0300-\u036f]/g, "");
            return /\b(ekran\w*|attels?|ekranattels?|redzam\w*|izskatas|novietoj\w*|krasa|fons|ikona|izkartoj\w*|visual|screenshot|screen|visible|look|layout|position|colour|color)\b/i.test(text);
        }

        function readUnsentDraft() {
            try {
                return String(localStorage.getItem(draftStorageKey) || "");
            } catch (error) {
                return "";
            }
        }

        function saveUnsentDraft(value) {
            const text = String(value || "").slice(0, 12000);
            try {
                if (text) {
                    localStorage.setItem(draftStorageKey, text);
                } else {
                    localStorage.removeItem(draftStorageKey);
                }
            } catch (error) {}
        }

        function clearUnsentDraft() {
            saveUnsentDraft("");
        }

        const restoredUnsentDraft = readUnsentDraft();
        if (restoredUnsentDraft) {
            input.value = restoredUnsentDraft;
        }

"""


def render_ls_elza_script_window_state_assets():
    """Return LS Elza opacity, window position, status, and busy-state helpers."""
    return r"""        function normalizeOpacity(value) {
            const number = Number(value);
            if (!Number.isFinite(number)) { return 50; }
            return Math.max(20, Math.min(100, Math.round(number)));
        }

        function applyBackgroundOpacity(value) {
            const opacity = normalizeOpacity(value);
            dialog.style.setProperty("--ls-elza-opacity", String(opacity / 100));
            if (opacitySlider) { opacitySlider.value = String(opacity); }
            if (opacityValue) { opacityValue.textContent = String(opacity) + "%"; }
            return opacity;
        }

        function readWindowState() {
            try {
                const raw = localStorage.getItem(windowStateStorageKey);
                const data = raw ? JSON.parse(raw) : {};
                return data && typeof data === "object" ? data : {};
            } catch (error) {
                return {};
            }
        }

        function writeWindowState(patch={}) {
            const current = readWindowState();
            const next = Object.assign({}, current, patch || {});
            try {
                localStorage.setItem(windowStateStorageKey, JSON.stringify(next));
            } catch (error) {}
            return next;
        }

        function clampDialogPosition(left, top) {
            const margin = 6;
            const maxLeft = Math.max(margin, window.innerWidth - dialog.offsetWidth - margin);
            const maxTop = Math.max(margin, window.innerHeight - dialog.offsetHeight - margin);
            return {
                left: Math.max(margin, Math.min(maxLeft, Number(left) || margin)),
                top: Math.max(margin, Math.min(maxTop, Number(top) || margin)),
            };
        }

        function applyStoredDialogPosition() {
            if (isDocked) { return; }
            const state = readWindowState();
            let left = Number(state.left);
            let top = Number(state.top);

            if (!Number.isFinite(left) || !Number.isFinite(top)) {
                left = Math.max(6, window.innerWidth - dialog.offsetWidth - 18);
                top = 72;
            }

            const point = clampDialogPosition(left, top);
            dialog.style.right = "auto";
            dialog.style.left = point.left + "px";
            dialog.style.top = point.top + "px";
        }

        function saveDialogPosition() {
            if (isDocked) { return; }
            const rect = dialog.getBoundingClientRect();
            writeWindowState({left: Math.round(rect.left), top: Math.round(rect.top)});
        }

        function setDockPosition(position, save=true) {
            if (!dockAvailable || !dockSlot || !dockSlot.parentElement) { return; }
            const parent = dockSlot.parentElement;
            const nextPosition = position === "top" ? "top" : "bottom";
            if (nextPosition === "top") {
                parent.insertBefore(dockSlot, parent.firstElementChild);
            } else {
                parent.appendChild(dockSlot);
            }
            dockSlot.dataset.dockPosition = nextPosition;
            if (save) { writeWindowState({dockPosition: nextPosition}); }
        }

        function applyStoredDockPosition() {
            if (!dockAvailable || !dockSlot) { return; }
            const state = readWindowState();
            setDockPosition(state.dockPosition === "top" ? "top" : "bottom", false);
        }

        function syncDockToggleState() {
            if (dockToggleButton) {
                dockToggleButton.hidden = !(dockAvailable && dockSlot);
                const label = isDocked ? "Float LS Elza" : "Dock LS Elza";
                dockToggleButton.textContent = isDocked ? "⇱" : "⇲";
                dockToggleButton.title = label;
                dockToggleButton.setAttribute("aria-label", label);
                dockToggleButton.setAttribute("aria-pressed", isDocked ? "true" : "false");
            }
            if (dockSlot) {
                dockSlot.classList.toggle("ls-elza-dock-empty", !isDocked);
            }
            document.body.classList.toggle("ls-elza-docked-active", isDocked);
            document.body.classList.toggle("ls-elza-floating-active", !isDocked);
        }

        function setDockedState(nextDocked, save=true) {
            const shouldDock = Boolean(nextDocked && dockAvailable && dockSlot);
            const previousScrollTop = historyBox ? Number(historyBox.scrollTop || 0) : 0;
            const previousScrollHeight = historyBox ? Number(historyBox.scrollHeight || 0) : 0;
            const previousClientHeight = historyBox ? Number(historyBox.clientHeight || 0) : 0;
            const wasNearBottom = (previousScrollHeight - previousScrollTop - previousClientHeight) <= 24;
            if (!shouldDock && isDocked) {
                const rect = dialog.getBoundingClientRect();
                writeWindowState({left: Math.round(rect.left), top: Math.round(rect.top)});
            }
            isDocked = shouldDock;
            if (isDocked) {
                modal.classList.add("ls-elza-docked");
                dockSlot.appendChild(modal);
                applyStoredDockPosition();
            } else {
                modal.classList.remove("ls-elza-docked");
                document.body.appendChild(modal);
            }
            syncDockToggleState();
            window.requestAnimationFrame(() => {
                if (!isDocked && modal.style.display === "block") {
                    applyStoredDialogPosition();
                }
                if (historyBox) {
                    historyBox.scrollTop = wasNearBottom
                        ? historyBox.scrollHeight
                        : Math.min(previousScrollTop, Math.max(0, historyBox.scrollHeight - historyBox.clientHeight));
                }
            });
            if (save) {
                writeWindowState({docked: isDocked});
            }
        }

        async function saveOpacitySetting(value) {
            const opacity = applyBackgroundOpacity(value);
            if (settingsStatus) { settingsStatus.textContent = "Saving..."; }
            try {
                const body = new URLSearchParams();
                body.set("opacity", String(opacity));
                const response = await fetch("/set-ls-elza-opacity", {
                    method: "POST",
                    headers: {"Content-Type": "application/x-www-form-urlencoded"},
                    body: body.toString(),
                });
                const data = await response.json();
                if (!response.ok || !data || !data.ok) {
                    throw new Error((data && data.error) || "Could not save opacity.");
                }
                applyBackgroundOpacity(data.opacity);
                if (settingsStatus) { settingsStatus.textContent = "Saved"; }
            } catch (error) {
                if (settingsStatus) {
                    settingsStatus.textContent = error.message || "Could not save opacity.";
                }
            }
        }

        applyBackgroundOpacity(serverBackgroundOpacity);

        function clearThinkingStatus() {
            statusLine.classList.remove("ls-elza-thinking");
            statusLine.removeAttribute("aria-label");
            statusLine.removeAttribute("title");
        }

        function setStatus(text, isError=false) {
            clearThinkingStatus();
            statusLine.textContent = text || "";
            statusLine.classList.toggle("error", Boolean(isError));
        }

        function showThinkingStatus(label="") {
            const accessibleLabel = label || "LS Elza is thinking";
            statusLine.classList.remove("error");
            statusLine.classList.add("ls-elza-thinking");
            statusLine.textContent = "";
            statusLine.setAttribute("role", "status");
            statusLine.setAttribute("aria-label", accessibleLabel);
            statusLine.title = accessibleLabel;

            const dots = document.createElement("span");
            dots.className = "ls-elza-thinking-dots";
            dots.setAttribute("aria-hidden", "true");
            for (let index = 0; index < 3; index += 1) {
                const dot = document.createElement("span");
                dot.className = "ls-elza-thinking-dot";
                dots.appendChild(dot);
            }
            statusLine.appendChild(dots);
        }

        function setBusy(busy, label="") {
            requestActive = Boolean(busy);
            sendButton.disabled = requestActive;
            newChatButton.disabled = requestActive;
            clearButton.disabled = requestActive;
            modeButtons.forEach((button) => {
                button.disabled = requestActive;
            });
            if (attachmentsBox) {
                attachmentsBox.querySelectorAll(".ls-elza-attachment-remove")
                    .forEach((button) => { button.disabled = requestActive; });
            }
            if (requestActive) {
                showThinkingStatus(label || "LS Elza is preparing a response...");
            } else if (statusLine.classList.contains("ls-elza-thinking")) {
                setStatus("");
            }
        }

"""


def render_ls_elza_script_attachment_state_assets():
    """Return LS Elza attachment list and image state helpers."""
    return r"""        function scrollHistoryToBottom() {
            historyBox.scrollTop = historyBox.scrollHeight;
        }

        function nextAttachmentId() {
            if (window.crypto && typeof window.crypto.randomUUID === "function") {
                return window.crypto.randomUUID();
            }
            return "image-" + Date.now() + "-" + Math.random().toString(16).slice(2);
        }

        function readFileAsDataUrl(file) {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(String(reader.result || ""));
                reader.onerror = () => reject(new Error("Could not read image."));
                reader.readAsDataURL(file);
            });
        }

        function renderPendingImages() {
            if (!attachmentsBox) { return; }
            attachmentsBox.innerHTML = "";
            attachmentsBox.classList.toggle("has-items", pendingImages.length > 0);
            pendingImages.forEach((item) => {
                const card = document.createElement("div");
                card.className = "ls-elza-attachment";
                card.title = item.name;

                const preview = document.createElement("img");
                preview.src = item.dataUrl;
                preview.alt = item.name;

                const name = document.createElement("div");
                name.className = "ls-elza-attachment-name";
                name.textContent = item.name;

                const remove = document.createElement("button");
                remove.type = "button";
                remove.className = "ls-elza-attachment-remove";
                remove.textContent = "×";
                remove.title = "Remove image";
                remove.setAttribute("aria-label", "Remove " + item.name);
                remove.disabled = requestActive;
                remove.addEventListener("click", () => {
                    if (requestActive) { return; }
                    pendingImages = pendingImages.filter(
                        (candidate) => candidate.id !== item.id
                    );
                    renderPendingImages();
                    setStatus(
                        pendingImages.length
                            ? String(pendingImages.length) + " image(s) ready."
                            : ""
                    );
                });

                card.appendChild(preview);
                card.appendChild(name);
                card.appendChild(remove);
                attachmentsBox.appendChild(card);
            });
        }

        function clearPendingImages() {
            pendingImages = [];
            renderPendingImages();
        }

"""


def render_ls_elza_script_capture_state_assets():
    """Return LS Elza UX screenshot capture state and handlers."""
    return r"""        function stopUxCapture() {
            if (!uxCaptureStream) { return; }
            uxCaptureStream.getTracks().forEach((track) => track.stop());
            uxCaptureStream = null;
        }

        async function requestUxCapture() {
            if (
                uxCaptureStream
                && uxCaptureStream.getVideoTracks().some(
                    (track) => track.readyState === "live"
                )
            ) {
                return true;
            }
            if (
                !navigator.mediaDevices
                || typeof navigator.mediaDevices.getDisplayMedia !== "function"
            ) {
                throw new Error(
                    "Chrome screen capture is not available. Use Ctrl+V to attach a screenshot."
                );
            }
            const stream = await navigator.mediaDevices.getDisplayMedia({
                video: {
                    displaySurface: "browser",
                    frameRate: {ideal: 1, max: 2},
                },
                audio: false,
                preferCurrentTab: true,
                selfBrowserSurface: "include",
                surfaceSwitching: "include",
            });
            const videoTrack = stream.getVideoTracks()[0];
            if (!videoTrack) {
                stream.getTracks().forEach((track) => track.stop());
                throw new Error("No window or tab was selected for UX review.");
            }
            uxCaptureStream = stream;
            videoTrack.addEventListener("ended", () => {
                if (uxCaptureStream !== stream) { return; }
                uxCaptureStream = null;
                if (selectedMode === "UX_REVIEW" || selectedMode === "TEST_REVIEW") {
                    setStatus(
                        "Screen sharing stopped. Turn the active mode off, then enable it again.",
                        true
                    );
                }
            }, {once: true});
            return true;
        }

        async function captureUxScreenshot(modeOverride="") {
            await requestUxCapture();
            const stream = uxCaptureStream;
            const captureMode = String(modeOverride || selectedMode).toUpperCase();
            const stopAfterCapture = captureMode === "UX_REVIEW";
            const video = document.createElement("video");
            let capturedImage = null;
            try {
                const videoTrack = stream && stream.getVideoTracks()[0];
                if (!videoTrack || videoTrack.readyState !== "live") {
                    throw new Error("UX screen sharing is not active.");
                }
                video.muted = true;
                video.playsInline = true;
                video.srcObject = stream;
                await new Promise((resolve, reject) => {
                    const timeoutId = window.setTimeout(
                        () => reject(new Error("The UX screenshot timed out.")),
                        5000
                    );
                    video.addEventListener("loadedmetadata", () => {
                        video.play().then(() => {
                            window.requestAnimationFrame(() => {
                                window.requestAnimationFrame(() => {
                                    window.clearTimeout(timeoutId);
                                    resolve();
                                });
                            });
                        }).catch(reject);
                    }, {once: true});
                });
                const sourceWidth = Number(video.videoWidth || 0);
                const sourceHeight = Number(video.videoHeight || 0);
                if (!sourceWidth || !sourceHeight) {
                    throw new Error("The selected UX screen has no visible video frame.");
                }
                const maxWidth = 1920;
                const scale = Math.min(1, maxWidth / sourceWidth);
                const canvas = document.createElement("canvas");
                canvas.width = Math.max(1, Math.round(sourceWidth * scale));
                canvas.height = Math.max(1, Math.round(sourceHeight * scale));
                const context2d = canvas.getContext("2d", {alpha: false});
                context2d.drawImage(video, 0, 0, canvas.width, canvas.height);
                const dataUrl = canvas.toDataURL("image/jpeg", 0.9);
                const commaIndex = dataUrl.indexOf(",");
                if (commaIndex < 0) {
                    throw new Error("The UX screenshot could not be encoded.");
                }
                capturedImage = {
                    name: "ls-ux-current-view.jpg",
                    mime_type: "image/jpeg",
                    data_base64: dataUrl.slice(commaIndex + 1),
                    detail: "high",
                };
            } finally {
                video.pause();
                video.srcObject = null;
                if (stopAfterCapture) {
                    if (uxCaptureStream === stream) {
                        uxCaptureStream = null;
                    }
                    if (stream) {
                        stream.getTracks().forEach((track) => track.stop());
                    }
                }
            }
            return capturedImage;
        }

"""


def render_ls_elza_script_state_assets():
    """Return LS Elza setup, state, window, opacity, and capture script."""
    return "".join((
        render_ls_elza_script_state_bootstrap_assets(),
        render_ls_elza_script_window_state_assets(),
        render_ls_elza_script_attachment_state_assets(),
        render_ls_elza_script_capture_state_assets(),
    ))


def render_ls_elza_script_message_rendering_assets():
    """Return LS Elza attachment and message-rendering script."""
    return r"""        async function addImageFiles(fileList) {
            if (requestActive) { return; }
            const files = Array.from(fileList || []).filter(Boolean);
            if (!files.length) { return; }

            for (const file of files) {
                if (pendingImages.length >= maxImagesPerMessage) {
                    setStatus("Attach no more than 4 images at once.", true);
                    break;
                }
                if (!allowedImageTypes.has(String(file.type || "").toLowerCase())) {
                    setStatus("LS Elza accepts PNG, JPEG and WebP images.", true);
                    continue;
                }
                if (!file.size || file.size > maxImageBytes) {
                    setStatus("Each image must be 5 MB or smaller.", true);
                    continue;
                }
                const pendingBytes = pendingImages.reduce(
                    (total, item) => total + Number(item.size || 0),
                    0
                );
                if (pendingBytes + file.size > maxTotalImageBytes) {
                    setStatus("Attached images must total 12 MB or less.", true);
                    break;
                }
                try {
                    const dataUrl = await readFileAsDataUrl(file);
                    const commaIndex = dataUrl.indexOf(",");
                    if (commaIndex < 0) { throw new Error("Unreadable image data."); }
                    pendingImages.push({
                        id: nextAttachmentId(),
                        name: String(file.name || "image").slice(0, 240),
                        mimeType: String(file.type || "").toLowerCase(),
                        size: Number(file.size || 0),
                        dataUrl: dataUrl,
                        dataBase64: dataUrl.slice(commaIndex + 1),
                        detail: "high",
                    });
                } catch (error) {
                    setStatus(error.message || "Could not read image.", true);
                }
            }
            renderPendingImages();
            if (pendingImages.length) {
                setStatus(
                    String(pendingImages.length)
                    + " image(s) ready · image data is not saved in chat history."
                );
            }
        }

        function appendInlineMarkdown(parent, value) {
            const text = String(value || "");
            const tokenPattern = /(\*\*[^*\n]+?\*\*|`[^`\n]+?`)/g;
            let cursor = 0;
            let match = null;

            while ((match = tokenPattern.exec(text)) !== null) {
                if (match.index > cursor) {
                    parent.appendChild(
                        document.createTextNode(text.slice(cursor, match.index))
                    );
                }

                const token = match[0];
                if (token.startsWith("**")) {
                    const strong = document.createElement("strong");
                    strong.textContent = token.slice(2, -2);
                    parent.appendChild(strong);
                } else {
                    const code = document.createElement("code");
                    code.textContent = token.slice(1, -1);
                    parent.appendChild(code);
                }
                cursor = tokenPattern.lastIndex;
            }

            if (cursor < text.length) {
                parent.appendChild(document.createTextNode(text.slice(cursor)));
            }
        }

        function markdownBlockType(line) {
            const value = String(line || "");
            if (/^```/.test(value)) { return "code"; }
            if (/^\s*[-+*]\s+/.test(value)) { return "unordered"; }
            if (/^\s*\d+[.)]\s+/.test(value)) { return "ordered"; }
            if (/^\s*>\s?/.test(value)) { return "quote"; }
            if (/^\s*#{1,3}\s+/.test(value)) { return "heading"; }
            return "text";
        }

        function renderMarkdownContent(container, value) {
            const source = String(value || "").replace(/\r\n?/g, "\n");
            const lines = source.split("\n");
            let index = 0;

            while (index < lines.length) {
                const line = lines[index];
                if (!line.trim()) {
                    index += 1;
                    continue;
                }

                const blockType = markdownBlockType(line);

                if (blockType === "code") {
                    index += 1;
                    const codeLines = [];
                    while (index < lines.length && !/^```/.test(lines[index])) {
                        codeLines.push(lines[index]);
                        index += 1;
                    }
                    if (index < lines.length) { index += 1; }
                    const pre = document.createElement("pre");
                    const code = document.createElement("code");
                    code.textContent = codeLines.join("\n");
                    pre.appendChild(code);
                    container.appendChild(pre);
                    continue;
                }

                if (blockType === "unordered" || blockType === "ordered") {
                    const list = document.createElement(
                        blockType === "unordered" ? "ul" : "ol"
                    );
                    const itemPattern = blockType === "unordered"
                        ? /^\s*[-+*]\s+/
                        : /^\s*\d+[.)]\s+/;

                    while (
                        index < lines.length
                        && markdownBlockType(lines[index]) === blockType
                    ) {
                        const item = document.createElement("li");
                        appendInlineMarkdown(item, lines[index].replace(itemPattern, ""));
                        list.appendChild(item);
                        index += 1;
                    }
                    container.appendChild(list);
                    continue;
                }

                if (blockType === "quote") {
                    const quote = document.createElement("blockquote");
                    const quoteLines = [];
                    while (
                        index < lines.length
                        && markdownBlockType(lines[index]) === "quote"
                    ) {
                        quoteLines.push(lines[index].replace(/^\s*>\s?/, ""));
                        index += 1;
                    }
                    quoteLines.forEach((quoteLine, quoteIndex) => {
                        if (quoteIndex) { quote.appendChild(document.createElement("br")); }
                        appendInlineMarkdown(quote, quoteLine);
                    });
                    container.appendChild(quote);
                    continue;
                }

                if (blockType === "heading") {
                    const heading = document.createElement("div");
                    heading.className = "ls-elza-markdown-heading";
                    appendInlineMarkdown(heading, line.replace(/^\s*#{1,3}\s+/, ""));
                    container.appendChild(heading);
                    index += 1;
                    continue;
                }

                const paragraph = document.createElement("p");
                let paragraphLineCount = 0;
                while (
                    index < lines.length
                    && lines[index].trim()
                    && markdownBlockType(lines[index]) === "text"
                ) {
                    if (paragraphLineCount) {
                        paragraph.appendChild(document.createElement("br"));
                    }
                    appendInlineMarkdown(paragraph, lines[index]);
                    paragraphLineCount += 1;
                    index += 1;
                }
                container.appendChild(paragraph);
            }
        }

        async function copyElzaAnswer(value) {
            const text = String(value || "");
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(text);
                return;
            }

            const helper = document.createElement("textarea");
            helper.value = text;
            helper.setAttribute("readonly", "");
            helper.style.position = "fixed";
            helper.style.left = "-9999px";
            helper.style.opacity = "0";
            document.body.appendChild(helper);
            helper.select();
            const copied = document.execCommand("copy");
            helper.remove();
            if (!copied) { throw new Error("Copy command was rejected."); }
        }

        const lsElzaAllowedViewParams = new Set([
            "query",
            "style_query",
            "workspace",
            "workspace_mode",
            "kind_filter",
            "category_filter",
            "category_mode",
            "local_family_filter",
            "like_filter",
            "local_audio_filter",
            "flag_filter",
            "tag_filter",
            "track_ids_filter",
            "sort_by",
            "sort_dir",
            "rows",
            "limit_value",
            "search_name",
            "search_lyrics",
            "search_prompt",
            "search_marks",
            "search_tags",
        ]);
        const lsElzaMultiValueViewParams = new Set([
            "workspace",
            "category_filter",
            "local_family_filter",
        ]);

"""


def render_ls_elza_view_action_assets():
    """Return LS Elza view-link and saved-view action helpers."""
    return r"""        function buildLsElzaViewUrlFromFragment(fragment) {
            let text = String(fragment || "").trim();
            if (!text) { return null; }
            text = text
                .replace(/^```[a-zA-Z0-9_-]*\s*/i, "")
                .replace(/```$/i, "")
                .trim();
            text = text.replace(/^[`'"\s]+|[`'"\s.,;:]+$/g, "");
            if (!text) { return null; }

            let queryPart = "";
            if (text.startsWith("?")) {
                queryPart = text.slice(1);
            } else if (text.startsWith("&")) {
                queryPart = text.slice(1);
            } else if (/^[A-Za-z0-9_]+=[^\s]+$/.test(text)) {
                queryPart = text;
            } else {
                return null;
            }

            let incoming = null;
            try {
                incoming = new URLSearchParams(queryPart);
            } catch (error) {
                return null;
            }
            if (!incoming || !Array.from(incoming.keys()).length) { return null; }

            const current = new URLSearchParams(window.location.search);
            let changed = false;
            const clearedMultiParams = new Set();
            incoming.forEach((value, key) => {
                if (!lsElzaAllowedViewParams.has(key)) { return; }
                if (lsElzaMultiValueViewParams.has(key)) {
                    if (!clearedMultiParams.has(key)) {
                        current.delete(key);
                        clearedMultiParams.add(key);
                    }
                    current.append(key, value);
                } else {
                    current.set(key, value);
                }
                changed = true;
            });
            if (!changed) { return null; }
            return window.location.pathname + "?" + current.toString();
        }

        function getLsElzaViewUrlFromAnswer(content) {
            const text = String(content || "");
            const candidates = [];
            const fullUrlPattern = /https?:\/\/[^\s<>"']+/g;
            let fullUrlMatch = null;
            while ((fullUrlMatch = fullUrlPattern.exec(text)) !== null) {
                candidates.push(fullUrlMatch[0].replace(/[\])}>.,;:]+$/g, ""));
            }
            const codePattern = /`([^`]*(?:\?|&|\\b)[A-Za-z0-9_]+=[^`]+)`/g;
            let match = null;
            while ((match = codePattern.exec(text)) !== null) {
                candidates.push(match[1]);
            }

            const fragmentPattern = /(?:^|\s)((?:[?&]|\\b)[A-Za-z0-9_]+=[A-Za-z0-9_.~%:-]+(?:&[A-Za-z0-9_]+=[A-Za-z0-9_.~%:-]+)*)/g;
            while ((match = fragmentPattern.exec(text)) !== null) {
                candidates.push(match[1]);
            }

            for (const candidate of candidates) {
                let fragment = candidate;
                if (/^https?:\/\//i.test(candidate)) {
                    try {
                        const parsed = new URL(candidate);
                        if (parsed.origin !== window.location.origin) { continue; }
                        fragment = parsed.search;
                    } catch (error) {
                        continue;
                    }
                }
                const url = buildLsElzaViewUrlFromFragment(fragment);
                if (url) { return url; }
            }
            return null;
        }

        function getLsElzaViewActionsContainer(bubble) {
            if (!bubble) { return null; }
            let container = bubble.querySelector(".ls-elza-view-actions");
            if (!container) {
                container = document.createElement("div");
                container.className = "ls-elza-view-actions";
                bubble.appendChild(container);
            }
            return container;
        }

        function addLsElzaViewActionButton(bubble, targetUrl, label) {
            if (!bubble || !targetUrl) { return; }
            if (bubble.querySelector('[data-ls-elza-action="open-view"]')) { return; }
            let url = null;
            try {
                url = new URL(targetUrl, window.location.origin);
            } catch (error) {
                return;
            }
            if (url.origin !== window.location.origin) { return; }

            const button = document.createElement("button");
            button.type = "button";
            button.className = "ls-elza-view-action";
            button.dataset.lsElzaAction = "open-view";
            button.textContent = String(label || "Atvērt sarakstu ar šo filtru").slice(0, 80);
            button.title = "Open the current LS list with this filter applied";
            button.addEventListener("click", () => {
                window.location.assign(url.pathname + url.search);
            });
            getLsElzaViewActionsContainer(bubble).appendChild(button);
        }

        function addLsElzaSaveViewActionButton(bubble, targetUrl, viewName, label) {
            if (!bubble || !targetUrl) { return; }
            if (bubble.querySelector('[data-ls-elza-action="save-view"]')) { return; }
            let url = null;
            try {
                url = new URL(targetUrl, window.location.origin);
            } catch (error) {
                return;
            }
            if (url.origin !== window.location.origin) { return; }

            const button = document.createElement("button");
            button.type = "button";
            button.className = "ls-elza-view-action ls-elza-view-action-secondary";
            button.dataset.lsElzaAction = "save-view";
            button.textContent = String(label || "Saglabāt kā View").slice(0, 80);
            button.title = "Save this read-only LS selection as a Saved View";
            button.addEventListener("click", () => {
                pendingLsElzaSaveViewButton = button;
                window.dispatchEvent(new CustomEvent("ls-elza-save-view-request", {
                    detail: {
                        url: url.pathname + url.search,
                        name: String(viewName || "LS Elza selection").slice(0, 80),
                    },
                }));
            });
            getLsElzaViewActionsContainer(bubble).appendChild(button);
        }

        window.addEventListener("ls-elza-view-saved", () => {
            const button = pendingLsElzaSaveViewButton;
            pendingLsElzaSaveViewButton = null;
            if (!button || !button.isConnected) { return; }
            button.textContent = "View saglabāts";
            button.title = "This LS Elza selection is saved";
            button.disabled = true;
        });

"""


def render_ls_elza_message_context_assets():
    """Return LS Elza message rendering and message-list helpers."""
    return r"""        function formatMessageTime(createdAt) {
            const raw = String(createdAt || "").trim();
            const date = raw ? new Date(raw) : new Date();
            if (Number.isNaN(date.getTime())) { return ""; }
            return date.toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"});
        }

        function addMessage(role, content, createdAt="") {
            const wrapper = document.createElement("div");
            const safeRole = role === "user" ? "user" : "assistant";
            wrapper.className = "ls-elza-message ls-elza-message-" + safeRole;

            const bubble = document.createElement("div");
            bubble.className = "ls-elza-bubble";
            renderMarkdownContent(bubble, content);

            const roleLabel = document.createElement("span");
            roleLabel.className = "ls-elza-message-role ls-mini-inline-role";
            if (safeRole === "user") {
                roleLabel.classList.add("ls-mini-question-prefix");
            }
            roleLabel.textContent = safeRole === "user" ? "Q:" : "A:";
            const firstParagraph = bubble.querySelector(":scope > p");
            if (firstParagraph) {
                firstParagraph.insertBefore(roleLabel, firstParagraph.firstChild);
            } else {
                bubble.insertBefore(roleLabel, bubble.firstChild);
            }

            if (safeRole === "assistant") {
                const answerViewUrl = getLsElzaViewUrlFromAnswer(content);
                addLsElzaViewActionButton(
                    bubble,
                    answerViewUrl,
                    "Atvērt sarakstu ar šo filtru"
                );
                addLsElzaSaveViewActionButton(
                    bubble,
                    answerViewUrl,
                    "LS Elza selection",
                    "Saglabāt kā View"
                );
            }

            const footer = document.createElement("div");
            footer.className = safeRole === "assistant"
                ? "ls-elza-message-footer ls-mini-answer-meta"
                : "ls-elza-message-footer";

            const timeLabel = document.createElement("span");
            timeLabel.className = safeRole === "assistant"
                ? "ls-elza-message-time ls-mini-message-time ls-mini-meta-control"
                : "ls-elza-message-time ls-mini-message-time";
            timeLabel.textContent = formatMessageTime(createdAt);
            footer.appendChild(timeLabel);

            if (safeRole === "assistant") {
                const copyButton = document.createElement("button");
                copyButton.type = "button";
                copyButton.className = "ls-elza-copy-btn ls-mini-meta-control";
                copyButton.innerHTML = `
                    <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
                        <rect x="5.25" y="2.75" width="7.5" height="8.5" rx="1.1"
                            fill="none" stroke="currentColor" stroke-width="1.35" />
                        <rect x="2.75" y="5.25" width="7.5" height="8" rx="1.1"
                            fill="none" stroke="currentColor" stroke-width="1.35" />
                    </svg>
                `;
                copyButton.title = "Copy this LS Elza answer";
                copyButton.setAttribute("aria-label", "Copy this LS Elza answer");
                copyButton.addEventListener("click", async (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    try {
                        await copyElzaAnswer(content);
                        copyButton.classList.add("copied");
                        copyButton.classList.remove("copy-failed");
                        copyButton.title = "Copied";
                        copyButton.setAttribute("aria-label", "Copied");
                    } catch (error) {
                        copyButton.classList.remove("copied");
                        copyButton.classList.add("copy-failed");
                        copyButton.title = "Copy failed";
                        copyButton.setAttribute("aria-label", "Copy failed");
                    }
                    setTimeout(() => {
                        if (!copyButton.isConnected) { return; }
                        copyButton.classList.remove("copied", "copy-failed");
                        copyButton.title = "Copy this LS Elza answer";
                        copyButton.setAttribute("aria-label", "Copy this LS Elza answer");
                    }, 1400);
                });
                footer.appendChild(copyButton);
            }

            bubble.appendChild(footer);
            wrapper.appendChild(bubble);
            historyBox.appendChild(wrapper);
        }

        function renderMessages(messages) {
            historyBox.innerHTML = "";
            if (!Array.isArray(messages) || !messages.length) {
                const empty = document.createElement("div");
                empty.className = "ls-elza-empty";
                empty.textContent = "No messages yet. Ask LS Elza about the current LocalSunoDb view.";
                historyBox.appendChild(empty);
                return;
            }
            messages.forEach((message) => {
                if (!message || !message.content) { return; }
                addMessage(message.role, message.content, message.created_at || "");
            });
            scrollHistoryToBottom();
        }

"""


def render_ls_elza_view_context_state_assets():
    """Return LS Elza chat ID and current-view context collectors."""
    return r"""        function saveChatId(value) {
            chatId = String(value || "");
            try {
                if (chatId) {
                    localStorage.setItem(chatStorageKey, chatId);
                } else {
                    localStorage.removeItem(chatStorageKey);
                }
            } catch (error) {}
        }

        function collectCurrentViewContext(selectedCount) {
            const view = Object.assign(
                {},
                serverViewContext && typeof serverViewContext === "object"
                    ? serverViewContext
                    : {}
            );
            const finderInput = document.getElementById("finder-search-input");
            const draftText = finderInput
                ? String(finderInput.value || "").trim()
                : "";
            const appliedText = String(view.search_text || "").trim();
            view.search_draft_text = draftText && draftText !== appliedText
                ? draftText
                : null;

            const searchFields = [];
            [
                ["finder-search-name", "Name"],
                ["finder-search-lyrics", "Lyrics"],
                ["finder-search-prompt", "Prompt"],
                ["finder-search-marks", "✶"],
                ["finder-search-tags", "#tag"],
            ].forEach(([id, label]) => {
                const field = document.getElementById(id);
                if (field && field.checked) { searchFields.push(label); }
            });
            if (searchFields.length) { view.search_fields = searchFields; }

            const tracksTable = document.getElementById("tracks-table");
            if (tracksTable) {
                view.loaded_row_count = tracksTable.querySelectorAll(
                    "tbody tr.track-row"
                ).length;
                view.wav_selection_mode = tracksTable.classList.contains(
                    "selection-mode"
                );
            } else if (view.loaded_row_count === undefined) {
                const localRows = document.querySelectorAll(
                    "main .table-wrap tbody tr"
                );
                if (localRows.length) { view.loaded_row_count = localRows.length; }
            }
            view.selected_row_count = Number(selectedCount || 0);
            return view;
        }

        function collectContext() {
            const checked = Array.from(
                document.querySelectorAll("tbody .track-check:checked")
            );
            const selectedTrackIds = checked
                .map((item) => String(item.value || "").trim())
                .filter((value) => value);

            let selectedTrackId = null;
            let title = null;
            let workspace = null;
            let mainCategory = null;
            let mainCategorySource = null;
            let trackKind = null;

            if (checked.length === 1) {
                selectedTrackId = selectedTrackIds[0] || null;
                const row = checked[0].closest("tr.track-row");
                if (row) {
                    const titleNode = row.querySelector(".title-link");
                    const workspaceNode = row.querySelector(".workspace-cell");
                    const categoryNode = row.querySelector(".main-category-toggle-btn");
                    const kindNode = row.querySelector(".kind-cell");
                    title = String(row.dataset.title || "").trim()
                        || (titleNode ? titleNode.textContent.trim() : null);
                    workspace = String(row.dataset.workspace || "").trim()
                        || (workspaceNode ? workspaceNode.textContent.trim() : null);
                    trackKind = String(row.dataset.kind || "").trim()
                        || (kindNode ? kindNode.textContent.trim() : null);
                    mainCategory = String(row.dataset.mainCategory || "").trim();
                    if (mainCategory) {
                        mainCategorySource = "row_data";
                    } else if (categoryNode) {
                        mainCategory = String(
                            categoryNode.dataset.category || ""
                        ).trim();
                        if (mainCategory) { mainCategorySource = "category_control"; }
                    }
                    if (!mainCategory && ["Song", "Instrumental"].includes(trackKind)) {
                        mainCategory = trackKind;
                        mainCategorySource = "track_kind_fallback";
                    }
                    mainCategory = mainCategory || null;
                }
            }

            const localFamilyInput = document.getElementById("local-family-title");
            const localFamilyTitle = localFamilyInput
                ? String(localFamilyInput.value || "").trim()
                : String(serverLocalFamilyTitle || "").trim();

            return {
                active_tab: configuredActiveTab,
                current_url: window.location.href,
                selected_track_id: selectedTrackId,
                selected_track_ids: selectedTrackIds,
                title: title,
                workspace: workspace,
                main_category: mainCategory,
                main_category_source: mainCategorySource,
                track_kind: trackKind,
                local_family_title: localFamilyTitle || null,
                app_version: appVersion,
                view: collectCurrentViewContext(selectedTrackIds.length),
            };
        }

"""


def render_ls_elza_context_line_assets():
    """Return LS Elza context-line refresh helpers."""
    return r"""        function updateContextLine() {
            const context = collectContext();
            const parts = [context.active_tab];
            if (context.selected_track_ids.length === 1) {
                parts.push(context.title || context.selected_track_id);
            } else if (context.selected_track_ids.length > 1) {
                parts.push(String(context.selected_track_ids.length) + " tracks selected");
            } else {
                parts.push("no track selected");
            }
            contextLine.textContent = parts.filter(Boolean).join(" · ");
            refreshModeButtons();
        }

        document.addEventListener("change", (event) => {
            const target = event.target;
            if (
                target instanceof HTMLInputElement
                && (
                    target.classList.contains("track-check")
                    || target.id === "check-all-table"
                )
            ) {
                updateContextLine();
                if (selectedMode !== "TRACK_DB") {
                    setStatus("");
                }
            }
        });

        document.addEventListener("click", (event) => {
            const target = event.target;
            if (
                target instanceof Element
                && target.closest("#wav-select-mode-btn")
            ) {
                window.requestAnimationFrame(updateContextLine);
            }
        });

"""


def render_ls_elza_script_view_context_assets():
    """Return LS Elza view-link, chat-state, and context script."""
    return "".join((
        render_ls_elza_view_action_assets(),
        render_ls_elza_message_context_assets(),
        render_ls_elza_view_context_state_assets(),
        render_ls_elza_context_line_assets(),
    ))


def render_ls_elza_script_service_assets():
    """Return LS Elza service, chat-loading, and local-answer script."""
    return r"""        async function callService(action, extra={}) {
            const payload = Object.assign({
                action: action,
                chat_id: chatId,
            }, extra || {});

            const response = await fetch("/ls-assistant-chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });

            let data = null;
            try {
                data = await response.json();
            } catch (error) {
                throw new Error("LS Elza returned an unreadable server response.");
            }

            if (!response.ok || !data || !data.ok) {
                throw new Error((data && data.error) || "LS Elza request failed.");
            }
            return data;
        }

        function appendLsViewAction(data) {
            const rawUrl = String(data && data.ls_view_url || "").trim();
            const saveUrl = String(data && data.ls_save_view_url || rawUrl).trim();
            if (!rawUrl && !saveUrl) { return; }
            const assistantMessages = historyBox.querySelectorAll(
                ".ls-elza-message-assistant"
            );
            const latest = assistantMessages[assistantMessages.length - 1];
            const bubble = latest ? latest.querySelector(".ls-elza-bubble") : null;
            addLsElzaViewActionButton(
                bubble,
                rawUrl,
                data.ls_view_label || "Atvērt sarakstu ar šo filtru"
            );
            addLsElzaSaveViewActionButton(
                bubble,
                saveUrl,
                data.ls_save_view_name || "LS Elza selection",
                data.ls_save_view_label || "Saglabāt kā View"
            );
            const footer = bubble ? bubble.querySelector(".ls-elza-message-footer") : null;
            if (footer) { bubble.appendChild(footer); }
        }

        function applyChatData(data) {
            if (data && data.chat_id) {
                saveChatId(data.chat_id);
            }
            if (data && data.local_exchange_only) {
                if (historyBox.querySelector(".ls-elza-empty")) {
                    historyBox.innerHTML = "";
                }
                addMessage("assistant", String(data.answer || ""));
                appendLsViewAction(data);
                scrollHistoryToBottom();
                return;
            }
            renderMessages(data && data.messages ? data.messages : []);
            appendLsViewAction(data);
        }

        async function loadCurrentChat() {
            setBusy(true, "Loading LS Elza chat...");
            try {
                const data = await callService("load");
                applyChatData(data);
                setStatus("");
            } catch (error) {
                renderMessages([]);
                setStatus(error.message || "Could not load LS Elza.", true);
            } finally {
                setBusy(false);
            }
        }

        function localLsElzaUiAnswer(message) {
            const text = String(message || "").trim().toLocaleLowerCase();

            if (
                /refresh\s*tracklist/i.test(text)
                && /\bupdate\b/i.test(text)
                && /(?:kāpēc|kapec|vienu un to pašu|to pašu|atkal|arvien)/i.test(text)
            ) {
                return [
                    "Tas ir sagaidāms, kamēr nav mainījušies abu preview avota dati.",
                    "",
                    "- **Refresh Tracklist** katru reizi nolasa jaunākos 100 ierakstus no jaunākās Suno darbvietas un salīdzina tos ar LS DB. Ja Suno nav jaunu ierakstu un LS nekas nav importēts vai ignorēts, rezultāts būs tas pats.",
                    "- **Update** atkārtoti meklē aktīvos LS ierakstus ar trūkstošiem metadata laukiem. Tā ir preview darbība; tikai saraksta atvēršana DB nemaina, tāpēc kandidāti paliek tie paši, līdz atzīmētajiem ierakstiem izpilda **Refresh selected metadata** vai mainās DB.",
                    "- Iepriekšējais Downloader skats tiek arī saglabāts, lai nepazustu pēc paneļa vai lapas maiņas, taču abu pogu nospiešana palaiž jaunu pārbaudi, nevis tikai atver saglabāto HTML.",
                    "",
                    "Tātad atkārtots saraksts pats par sevi nav kļūda. Aizdomīgi būtu tad, ja Suno vai DB dati ir mainījušies, bet pēc jaunas pārbaudes skaitļi un rindas nemainās.",
                ].join("\n");
            }

            if (
                /(?:ls\s*elza|elza).*(?:iestat|settings|caurspīd|opacity)/i.test(text)
                || /(?:background opacity|elzas? caurspīd)/i.test(text)
            ) {
                return [
                    "Pašlaik **LS Elza Settings** maina tikai paneļa fona caurspīdību.",
                    "",
                    "- **Background opacity** maina sarunas un ievades virsmu caurspīdību; teksts paliek pilnībā redzams.",
                    "- Iestatījums tiek saglabāts lokāli LocalSunoDb iestatījumos.",
                    "- Tas nemaina Elzas modeli, API, DB piekļuvi vai atbilžu saturu.",
                ].join("\n");
            }

            if (
                /(?:new chat|clear).*(?:ko dara|nozīmē|atšķir|paskaidro|izskaidro)/i.test(text)
                || /(?:ko dara|paskaidro|izskaidro).*(?:new chat|clear)/i.test(text)
            ) {
                return [
                    "**New chat** sāk jaunu, atsevišķu sarunu; iepriekšējā saruna paliek lokālajā vēsturē.",
                    "",
                    "**Clear** izdzēš tikai pašreizējās sarunas ziņas. Tas nemaina LS datubāzi, failus vai atlasīto dziesmu.",
                ].join("\n");
            }

            if (
                /(?:attach|pievienot attēl|ielikt attēl|ctrl\+v|ievilkt attēl)/i.test(text)
                && /(?:elza|čat|chat|attēl)/i.test(text)
            ) {
                return [
                    "Attēlu Elzai var pievienot ar `Ctrl+V` vai ievelkot to Elzas logā.",
                    "",
                    "Attēls tiek izmantots tikai konkrētajam pieprasījumam; attēla dati sarunas vēsturē netiek saglabāti.",
                ].join("\n");
            }

            if (
                /(?:ko elza var|ko var ls elza|elza.*(?:mainīt|rakstīt).*(?:db|datubāz|fail))/i.test(text)
            ) {
                return "LS Elza tikai konsultē. Tā pati nemaina datubāzi, failus, Local family, Stems saites vai citus LS datus.";
            }

            return "";
        }

        function saferConsultationPrompt(message) {
            const source = String(message || "").trim();
            const verbMap = {
                "izdzēs": "izdzēst",
                "maini": "mainīt",
                "pārsauc": "pārsaukt",
                "pārvieto": "pārvietot",
                "lejupielādē": "lejupielādēt",
                "palaid": "palaist",
                "izpildi": "izpildīt",
                "salabo": "salabot",
                "atjauno": "atjaunot",
                "izveido": "izveidot",
                "pievieno": "pievienot",
                "noņem": "noņemt",
            };
            const match = source.match(
                /^(izdzēs|maini|pārsauc|pārvieto|lejupielādē|palaid|izpildi|salabo|atjauno|izveido|pievieno|noņem)\b(.*)$/i
            );
            if (!match) { return ""; }
            const infinitive = verbMap[match[1].toLocaleLowerCase()] || match[1];
            const rest = String(match[2] || "").trim();
            return (
                "Paskaidro, kā droši " + infinitive
                + (rest ? " " + rest : " šo darbību")
                + ". Pati neko nemaini."
            );
        }

        function isLocalLsSelectionCommand(message) {
            const source = String(message || "").trim();
            const plain = source
                .toLocaleLowerCase()
                .normalize("NFD")
                .replace(/[\u0300-\u036f]/g, "");
            const hasCommand = /\b(paradi|atlasi|atrodi|atver|uzskaiti|ieliec|dabut|show|find|list|open)\b/i.test(plain);
            const hasSupportedFilter = (
                /\bliked\b|\blokal\w*\s+audio\b|\binstrumental\w*\b|\bstems?\b|\bkarodz\w*\b|\bflags?\b|\bzvaigzn\w*\b|\bwav\b|\b(?:upload|uplod|uploads?)\b/i.test(plain)
                || /(?<!\d)[0-5]\s*\+\s*\*/.test(plain)
                || /(?<!\w)#[\w-]+/u.test(source)
                || /(?:workspace|darbviet\w*|local\s+family|nosaukum\w*)\s*(?::|=)?\s*[\"“']/i.test(source)
            );
            return hasCommand && hasSupportedFilter;
        }

        function reviewLsElzaPrompt(message, imageCount) {
            const text = String(message || "").trim();
            const folded = text.toLocaleLowerCase();
            const plain = folded.normalize("NFD").replace(/[\u0300-\u036f]/g, "");

            if (
                Number(imageCount || 0) === 0
                && isLocalLsSelectionCommand(text)
            ) {
                return {
                    mode: "local_db",
                    queryId: "selection",
                };
            }

            const localAnswer = Number(imageCount || 0) === 0
                ? localLsElzaUiAnswer(text)
                : "";
            if (localAnswer) {
                return {mode: "local", answer: localAnswer};
            }

            if (
                /(?:openai_api_key|api\s*key|api atslēg|system prompt|sistēmas prompt)/i.test(folded)
                || /(?:ignore|ignorē|apej|atspējo).*(?:instruction|instrukc|droš|safety)/i.test(folded)
                || /(?:izpildi|execute|run).*(?:powershell|python|sql|shell)/i.test(folded)
            ) {
                return {
                    mode: "block",
                    warning: "Pieprasījums nav nosūtīts: tas skar API atslēgu, sistēmas instrukcijas vai koda izpildi. Pārformulē to kā drošas, read-only konsultācijas jautājumu.",
                };
            }

            if (
                Number(imageCount || 0) === 0
                && text.length <= 90
                && /^(ko darīt|kāpēc|kas tas|izskaidro šo|paskaidro šo|pārbaudi šo|salabo šo|dari to|turpini)[\s?!.]*$/i.test(folded)
            ) {
                return {
                    mode: "block",
                    warning: "Pieprasījums nav nosūtīts: nav skaidrs, uz ko attiecas “šis/to”. Pievieno objektu, Track ID, funkcijas nosaukumu vai attēlu.",
                };
            }

            if (
                /(?:pārbaudi|izlasi|nolasi|analizē|uzskaiti|parādi)\s+(?:visu|visus|pilnu|pilnīgi visu).*(?:db|datubāz|kodu|fail)/i.test(folded)
                || /(?:read|inspect|analyze|list)\s+(?:all|entire|full).*(?:database|code|files?)/i.test(folded)
            ) {
                return {
                    mode: "block",
                    warning: "Pieprasījums nav nosūtīts: tas ir pārāk plašs read-only pārbaudei. Norādi vienu Track ID, Workspace, lauku, funkciju vai konkrētu jautājumu.",
                };
            }

            const saferPrompt = saferConsultationPrompt(text);
            if (saferPrompt) {
                return {
                    mode: "rewrite",
                    rewrite: saferPrompt,
                    warning: "Elza pati neko nemaina. Drošāks konsultācijas formulējums ir ievietots laukā; pārbaudi to un nospied Send vēlreiz.",
                };
            }

            return {mode: "send"};
        }

        function appendLocalLsElzaExchange(userText, answerText) {
            if (historyBox.querySelector(".ls-elza-empty")) {
                historyBox.innerHTML = "";
            }
            addMessage("user", userText);
            addMessage("assistant", answerText);
            scrollHistoryToBottom();
            setStatus("Answered locally · OpenAI API and read-only tools were not used.");
        }

        function safeReadonlyLimitAnswer(message) {
            const text = String(message || "").trim();
            const isUiOrCodeQuestion = /(?:refresh\s*tracklist|\bupdate\b|poga|panel|logs|lodziņ|funkcij|ui|kods?)/i.test(text);
            if (isUiOrCodeQuestion) {
                return [
                    "Read-only koda pārbaude sasniedza drošības limitu pirms secinājuma.",
                    "",
                    "Šis ir jautājums par LS funkcijas darbību, tāpēc **Track ID vai Workspace nav vajadzīgs**. Elza pieprasījumu automātiski neatkārtos un DB nemainīs. Lai turpinātu, jautājumā pietiek norādīt vienu konkrētu pogu vai funkciju; piemēram: `Ko dara Refresh Tracklist?`",
                ].join("\n");
            }
            return [
                "Read-only DB pārbaude sasniedza drošības limitu pirms secinājuma.",
                "",
                "Elza pieprasījumu automātiski neatkārtos un DB nemainīs. Sašaurini pārbaudi līdz vienam Track ID, Workspace, laukam vai vienai skaidri formulētai atlasei.",
            ].join("\n");
        }

"""


def render_ls_elza_script_chat_actions_assets():
    """Return LS Elza send, new-chat, and clear-chat actions."""
    return r"""        async function sendMessage() {
            if (requestActive) { return; }
            let message = String(input.value || "").trim();
            const outgoingImages = pendingImages.map((item) => ({
                name: item.name,
                mime_type: item.mimeType,
                data_base64: item.dataBase64,
                detail: item.detail || "high",
            }));
            if (!message && outgoingImages.length) {
                message = "Lūdzu, analizē pievienoto attēlu.";
            }
            if (!message) {
                setStatus("Write a message or attach an image before sending.", true);
                input.focus();
                return;
            }

            clearClarifiedDraftState();
            const promptReview = reviewLsElzaPrompt(
                message,
                outgoingImages.length
            );
            if (promptReview.mode === "local") {
                input.value = "";
                setBusy(true, "LS Elza is saving the local answer...");
                try {
                    const data = await callService("local_exchange", {
                        message: message,
                        answer: promptReview.answer,
                    });
                    applyChatData(data);
                    clearUnsentDraft();
                    setStatus("Answered locally · OpenAI API and read-only tools were not used.");
                } catch (error) {
                    input.value = message;
                    saveUnsentDraft(message);
                    setStatus(error.message || "Could not save the local Elza answer.", true);
                } finally {
                    setBusy(false);
                    input.focus();
                }
                return;
            }
            if (promptReview.mode === "rewrite") {
                input.value = promptReview.rewrite;
                saveUnsentDraft(input.value);
                setStatus(promptReview.warning, true);
                input.focus();
                input.select();
                return;
            }
            if (promptReview.mode === "block") {
                setStatus(promptReview.warning, true);
                input.focus();
                return;
            }

            const textAssessment = assessLsElzaQuestion(
                message,
                collectContext()
            );
            const questionAssessment = outgoingImages.length
                && textAssessment.ambiguous
                ? {mode: "UX_REVIEW", ambiguous: false}
                : textAssessment;
            if (questionAssessment.ambiguous) {
                setBusy(true, "LS Elza is clarifying the question...");
                try {
                    const clarification = await callService("clarify", {
                        message: message,
                        context: collectContext(),
                    });
                    applyChatData(clarification);
                    const rewritten = String(
                        clarification && clarification.rewritten_question || ""
                    ).trim();
                    if (rewritten) {
                        setClarifiedDraft(rewritten);
                    } else {
                        input.value = message;
                        saveUnsentDraft(message);
                    }
                } catch (error) {
                    input.value = message;
                    saveUnsentDraft(message);
                    if (historyBox.querySelector(".ls-elza-empty")) {
                        historyBox.innerHTML = "";
                    }
                    addMessage(
                        "assistant",
                        "Nevarēju droši pārformulēt jautājumu. Norādi, ko tieši vēlies noskaidrot un par kuru LS funkciju, skatu vai izvēlēto dziesmu ir jautājums."
                    );
                    scrollHistoryToBottom();
                } finally {
                    setBusy(false);
                    input.focus();
                }
                return;
            }

            const automaticMode = questionAssessment.mode;
            const requestMode = selectedMode || automaticMode;

            if (
                promptReview.mode !== "local_db"
                && needsLsElzaVisualContext(message, requestMode)
            ) {
                try {
                    setStatus(
                        requestMode === "TEST_REVIEW"
                            ? "Capturing the current LS window for function testing..."
                            : "Capturing the current LS window for UX review..."
                    );
                    outgoingImages.push(await captureUxScreenshot(requestMode));
                } catch (error) {
                    console.warn("LS Elza automatic screen capture failed", error);
                    setStatus("Screen capture was not available. Attach an image if needed.");
                    return;
                }
            }

            if (historyBox.querySelector(".ls-elza-empty")) {
                historyBox.innerHTML = "";
            }
            const displayMessage = outgoingImages.length
                ? message
                    + "\n\n📎 Attēli šajā ziņā: "
                    + String(outgoingImages.length)
                    + " (attēlu dati nav saglabāti)."
                : message;
            addMessage("user", displayMessage);
            scrollHistoryToBottom();
            input.value = "";
            updateContextLine();
            const serviceAction = promptReview.mode === "local_db"
                ? "local_readonly"
                : "send";
            setBusy(
                true,
                serviceAction === "local_readonly"
                    ? "LS is reading the local database..."
                    : "LS Elza is preparing a response..."
            );

            try {
                const data = await callService(serviceAction, {
                    message: message,
                    context: collectContext(),
                    images: outgoingImages,
                    query_id: promptReview.queryId || "",
                    selected_mode: selectedMode,
                });
                clearPendingImages();
                applyChatData(data);
                clearUnsentDraft();
                setStatus("");
            } catch (error) {
                if (!input.value) { input.value = message; }
                saveUnsentDraft(input.value);
                const errorText = String(error && error.message || "");
                if (/safe read-only tool-call limit/i.test(errorText)) {
                    addMessage("assistant", safeReadonlyLimitAnswer(message));
                    scrollHistoryToBottom();
                    setStatus(
                        "Read-only pārbaude apturēta; Elza paskaidroja nākamo soli."
                    );
                } else {
                    console.warn("LS Elza request failed", error);
                    setStatus("Elza could not finish this request.");
                }
            } finally {
                setBusy(false);
                input.focus();
            }
        }

        async function startNewChat() {
            if (requestActive) { return; }
            setBusy(true, "Starting a new chat...");
            try {
                const data = await callService("new_chat");
                clearPendingImages();
                applyChatData(data);
                setStatus("");
                input.focus();
            } catch (error) {
                setStatus(error.message || "Could not start a new chat.", true);
            } finally {
                setBusy(false);
            }
        }

        async function clearCurrentChat() {
            if (requestActive) { return; }
            if (!window.confirm("Clear all messages in the current LS Elza chat?")) {
                return;
            }
            setBusy(true, "Clearing the current chat...");
            try {
                const data = await callService("clear");
                clearPendingImages();
                applyChatData(data);
                setStatus("");
                input.focus();
            } catch (error) {
                setStatus(error.message || "Could not clear the chat.", true);
            } finally {
                setBusy(false);
            }
        }

"""


def render_ls_elza_script_window_interaction_assets():
    """Return LS Elza window, mode, attachment, and settings interactions."""
    return r"""        function syncSidebarChoiceState() {
            const isOpen = modal.getAttribute("aria-hidden") === "false";
            openButton.classList.toggle("active", isOpen);
            openButton.setAttribute("aria-expanded", isOpen ? "true" : "false");
        }

        function openModal(focusInput=true) {
            document.querySelectorAll(".top-dropdown").forEach((menu) => {
                menu.classList.add("hidden");
            });
            updateContextLine();
            modal.style.display = "block";
            modal.setAttribute("aria-hidden", "false");
            if (
                isDocked &&
                dockSlot &&
                window.LS &&
                window.LS.rightDock &&
                typeof window.LS.rightDock.activate === "function"
            ) {
                window.LS.rightDock.activate(dockSlot);
            }
            syncSidebarChoiceState();
            writeWindowState({open: true});
            window.requestAnimationFrame(() => {
                if (isDocked && dockSlot) {
                    if (focusInput) {
                        dockSlot.scrollIntoView({
                            behavior: "smooth",
                            block: "nearest",
                        });
                    }
                } else {
                    applyStoredDialogPosition();
                }
                if (!chatLoaded) {
                    chatLoaded = true;
                    loadCurrentChat().then(() => {
                        if (focusInput) { input.focus(); }
                    });
                } else if (focusInput) {
                    input.focus();
                }
            });
        }

        function closeModal() {
            saveDialogPosition();
            modal.style.display = "none";
            modal.setAttribute("aria-hidden", "true");
            syncSidebarChoiceState();
            writeWindowState({open: false});
            if (settingsPanel) { settingsPanel.classList.remove("open"); }
        }

        openButton.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            openModal();
        });
        closeButton.addEventListener("click", closeModal);
        if (dockToggleButton) {
            dockToggleButton.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                setDockedState(!isDocked);
                openModal(false);
            });
        }
        newChatButton.addEventListener("click", startNewChat);
        clearButton.addEventListener("click", clearCurrentChat);
        sendButton.addEventListener("click", sendMessage);

        modeButtons.forEach((button) => {
            button.addEventListener("click", async (event) => {
                event.preventDefault();
                event.stopPropagation();
                if (requestActive) { return; }
                const buttonMode = String(
                    button.dataset.lsElzaMode || ""
                ).toUpperCase();
                if (selectedMode === buttonMode) {
                    setSelectedMode("");
                    if (buttonMode === "UX_REVIEW" || buttonMode === "TEST_REVIEW") {
                        stopUxCapture();
                    }
                    setStatus("");
                    input.focus();
                    return;
                }
                if (buttonMode === "UX_REVIEW" || buttonMode === "TEST_REVIEW") {
                    try {
                        setStatus(
                            "Select this LS tab or window once. The active mode will capture a fresh frame for each question."
                        );
                        await requestUxCapture();
                    } catch (error) {
                        setSelectedMode("");
                        setStatus(
                            error.message || "UX screen sharing was not enabled.",
                            true
                        );
                        input.focus();
                        return;
                    }
                } else if (
                    buttonMode === "TRACK_DB"
                    && collectContext().selected_track_ids.length !== 1
                ) {
                    setSelectedMode("");
                    setStatus("Select exactly one track before using Track mode.", true);
                    input.focus();
                    return;
                }
                setSelectedMode(buttonMode);
                setStatus(
                    buttonMode === "UX_REVIEW"
                        ? "UX review is ready · the current LS view will be attached automatically."
                        : buttonMode === "TEST_REVIEW"
                            ? "Test mode is ready · describe the action and expected result. The current LS view will be attached automatically."
                            : buttonMode === "TRACK_DB"
                                ? "Track mode is ready · ask about the selected track."
                                : buttonMode === "LS_CODE"
                                    ? "Code mode is ready · read-only analysis of the current LS source."
                                : ""
                );
                input.focus();
            });
        });

        input.addEventListener("paste", (event) => {
            const items = Array.from(
                event.clipboardData && event.clipboardData.items
                    ? event.clipboardData.items
                    : []
            );
            const files = items
                .filter((item) => String(item.type || "").startsWith("image/"))
                .map((item) => item.getAsFile())
                .filter(Boolean);
            if (files.length) { addImageFiles(files); }
        });

        if (dialog) {
            const hasImageFiles = (event) => Array.from(
                event.dataTransfer && event.dataTransfer.items
                    ? event.dataTransfer.items
                    : []
            ).some((item) => (
                item.kind === "file"
                && String(item.type || "").startsWith("image/")
            ));

            dialog.addEventListener("dragenter", (event) => {
                if (!hasImageFiles(event)) { return; }
                event.preventDefault();
                imageDragDepth += 1;
                dialog.classList.add("image-dragover");
            });
            dialog.addEventListener("dragover", (event) => {
                if (!hasImageFiles(event)) { return; }
                event.preventDefault();
                if (event.dataTransfer) { event.dataTransfer.dropEffect = "copy"; }
            });
            dialog.addEventListener("dragleave", () => {
                imageDragDepth = Math.max(0, imageDragDepth - 1);
                if (!imageDragDepth) { dialog.classList.remove("image-dragover"); }
            });
            dialog.addEventListener("drop", (event) => {
                if (!hasImageFiles(event)) { return; }
                event.preventDefault();
                imageDragDepth = 0;
                dialog.classList.remove("image-dragover");
                addImageFiles(event.dataTransfer.files);
            });
        }

        if (settingsToggle && settingsPanel) {
            settingsToggle.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                settingsPanel.classList.toggle("open");
                if (settingsStatus) { settingsStatus.textContent = ""; }
            });
        }

        if (opacitySlider) {
            opacitySlider.addEventListener("input", () => {
                applyBackgroundOpacity(opacitySlider.value);
                if (settingsStatus) { settingsStatus.textContent = ""; }
            });
            opacitySlider.addEventListener("change", () => {
                saveOpacitySetting(opacitySlider.value);
            });
        }

"""


def render_ls_elza_script_drag_interaction_assets():
    """Return LS Elza floating movement and dock reordering interactions."""
    return r"""        if (dragHandle) {
            dragHandle.addEventListener("pointerdown", (event) => {
                if (event.button !== 0) { return; }
                if (event.target.closest("button, input, textarea, select, a")) { return; }
                if (isDocked) {
                    if (!dockSlot || !dockSlot.parentElement) { return; }
                    const currentPosition = (
                        dockSlot.dataset.dockPosition === "top"
                    ) ? "top" : "bottom";
                    const parent = dockSlot.parentElement;
                    const rect = dockSlot.getBoundingClientRect();
                    const placeholder = document.createElement("div");
                    placeholder.className = "ls-elza-dock-placeholder";
                    placeholder.dataset.dockTarget = currentPosition;
                    placeholder.style.height = Math.max(94, Math.round(rect.height)) + "px";
                    parent.insertBefore(placeholder, dockSlot);
                    dragState = {
                        pointerId: event.pointerId,
                        docked: true,
                        startY: event.clientY,
                        currentPosition,
                        targetPosition: currentPosition,
                        parent,
                        placeholder,
                        startTop: rect.top,
                        startLeft: rect.left,
                        width: rect.width,
                    };
                    document.body.appendChild(dockSlot);
                    dragHandle.setPointerCapture(event.pointerId);
                    dockSlot.classList.add("ls-elza-dock-dragging");
                    dockSlot.style.position = "fixed";
                    dockSlot.style.left = rect.left + "px";
                    dockSlot.style.top = rect.top + "px";
                    dockSlot.style.width = rect.width + "px";
                    dockSlot.style.margin = "0";
                    dockSlot.style.zIndex = "40000";
                    event.preventDefault();
                    return;
                }
                const rect = dialog.getBoundingClientRect();
                dragState = {
                    pointerId: event.pointerId,
                    docked: false,
                    startX: event.clientX,
                    startY: event.clientY,
                    left: rect.left,
                    top: rect.top,
                };
                dragHandle.setPointerCapture(event.pointerId);
                event.preventDefault();
            });

            dragHandle.addEventListener("pointermove", (event) => {
                if (!dragState || dragState.pointerId !== event.pointerId) { return; }
                if (dragState.docked) {
                    const deltaY = event.clientY - dragState.startY;
                    let targetPosition = dragState.currentPosition;
                    if (deltaY <= -28) {
                        targetPosition = "top";
                    } else if (deltaY >= 28) {
                        targetPosition = "bottom";
                    }
                    const targetChanged = targetPosition !== dragState.targetPosition;
                    dragState.targetPosition = targetPosition;
                    dockSlot.style.top = dragState.startTop + deltaY + "px";
                    dockSlot.classList.toggle(
                        "ls-elza-dock-target-top",
                        targetPosition === "top"
                    );
                    dockSlot.classList.toggle(
                        "ls-elza-dock-target-bottom",
                        targetPosition === "bottom"
                    );
                    if (targetChanged && dragState.placeholder && dragState.parent) {
                        dragState.placeholder.dataset.dockTarget = targetPosition;
                        if (targetPosition === "top") {
                            dragState.parent.insertBefore(
                                dragState.placeholder,
                                dragState.parent.firstElementChild
                            );
                            dragState.parent.scrollTop = 0;
                        } else {
                            dragState.parent.appendChild(dragState.placeholder);
                            dragState.parent.scrollTop = dragState.parent.scrollHeight;
                        }
                    }
                    event.preventDefault();
                    return;
                }
                const point = clampDialogPosition(
                    dragState.left + event.clientX - dragState.startX,
                    dragState.top + event.clientY - dragState.startY
                );
                dialog.style.right = "auto";
                dialog.style.left = point.left + "px";
                dialog.style.top = point.top + "px";
            });

            const finishDrag = (event, cancelled=false) => {
                if (!dragState || dragState.pointerId !== event.pointerId) { return; }
                const finishedState = dragState;
                try { dragHandle.releasePointerCapture(event.pointerId); } catch (error) {}
                dragState = null;
                if (finishedState.docked) {
                    const nextPosition = cancelled
                        ? finishedState.currentPosition
                        : finishedState.targetPosition;
                    const parent = finishedState.parent;
                    const placeholder = finishedState.placeholder;
                    if (cancelled && parent && placeholder) {
                        placeholder.dataset.dockTarget = nextPosition;
                        if (nextPosition === "top") {
                            parent.insertBefore(placeholder, parent.firstElementChild);
                        } else {
                            parent.appendChild(placeholder);
                        }
                    }
                    if (parent && placeholder) {
                        parent.insertBefore(dockSlot, placeholder);
                        placeholder.remove();
                    }
                    dockSlot.style.position = "";
                    dockSlot.style.left = "";
                    dockSlot.style.top = "";
                    dockSlot.style.width = "";
                    dockSlot.style.margin = "";
                    dockSlot.style.zIndex = "";
                    dockSlot.classList.remove(
                        "ls-elza-dock-dragging",
                        "ls-elza-dock-target-top",
                        "ls-elza-dock-target-bottom"
                    );
                    dockSlot.dataset.dockPosition = nextPosition;
                    if (!cancelled) {
                        writeWindowState({dockPosition: nextPosition});
                        dockSlot.scrollIntoView({
                            behavior: "smooth",
                            block: nextPosition === "top" ? "start" : "nearest",
                        });
                    }
                    return;
                }
                saveDialogPosition();
            };
            dragHandle.addEventListener("pointerup", finishDrag);
            dragHandle.addEventListener("pointercancel", (event) => {
                finishDrag(event, true);
            });
        }

"""


def render_ls_elza_script_terminal_events_assets():
    """Return LS Elza input, document, resize, and startup events."""
    return r"""        input.addEventListener("keydown", (event) => {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                sendMessage();
            }
        });

        input.addEventListener("input", () => {
            if (clarifiedDraftActive) {
                clearClarifiedDraftState();
            }
            saveUnsentDraft(input.value);
        });

        window.addEventListener("beforeunload", () => {
            saveUnsentDraft(input.value);
        });

        document.addEventListener("change", (event) => {
            if (event.target && event.target.classList.contains("track-check")) {
                if (modal.style.display === "block") { updateContextLine(); }
            }
        });

        window.addEventListener("resize", () => {
            if (isDocked) { return; }
            if (modal.style.display !== "block") { return; }
            applyStoredDialogPosition();
            saveDialogPosition();
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && modal.style.display === "block") {
                event.preventDefault();
                closeModal();
            }
        });

        syncSidebarChoiceState();
        const initialWindowState = readWindowState();
        setDockedState(
            Boolean(dockAvailable && dockSlot && initialWindowState.docked === true),
            false
        );
        if (initialWindowState.open) {
            openModal(false);
        }
    })();
    </script>
    """


def render_ls_elza_script_interaction_assets():
    """Compose LS Elza interaction JavaScript from focused assets."""
    return (
        render_ls_elza_script_chat_actions_assets()
        + render_ls_elza_script_window_interaction_assets()
        + render_ls_elza_script_drag_interaction_assets()
        + render_ls_elza_script_terminal_events_assets()
    )


def render_ls_elza_script_assets():
    """Compose the static LS Elza browser script from focused assets."""
    return (
        render_ls_elza_script_state_assets()
        + render_ls_elza_script_message_rendering_assets()
        + render_ls_elza_script_view_context_assets()
        + render_ls_elza_script_service_assets()
        + render_ls_elza_script_interaction_assets()
    )


def render_ls_elza_assets(
    active_tab,
    view_context=None,
    docked=False,
    *,
    local_family_title="",
    app_version="",
    opacity=50,
):
    template = (
        render_ls_elza_style_assets()
        + render_ls_elza_dialog_markup()
        + render_ls_elza_script_assets()
    )

    replacements = {
        "__LS_ELZA_ACTIVE_TAB_JSON__": ls_elza_json_for_script(str(active_tab or "")),
        "__LS_ELZA_LOCAL_FAMILY_JSON__": ls_elza_json_for_script(local_family_title),
        "__LS_ELZA_APP_VERSION_JSON__": ls_elza_json_for_script(app_version),
        "__LS_ELZA_VIEW_CONTEXT_JSON__": ls_elza_json_for_script(
            view_context if isinstance(view_context, dict) else {}
        ),
        "__LS_ELZA_OPACITY_JSON__": ls_elza_json_for_script(opacity),
        "__LS_ELZA_OPACITY_VALUE__": str(opacity),
        "__LS_ELZA_DOCKED_JSON__": "true" if docked else "false",
    }
    for marker, value in replacements.items():
        template = template.replace(marker, value)
    return template
