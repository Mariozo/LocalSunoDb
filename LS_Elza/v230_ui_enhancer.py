"""Elza v2.32 composer and microphone-level UI.

The existing Local Suno STT recorder remains the source of audio/transcription.
This enhancer only restructures the composer and visualizes the real microphone
MediaStream through Web Audio AnalyserNode.
"""

MARKER = 'data-elza-v232'

_STYLE = r"""
<style data-elza-v232="style">
.ls-elza-compose { position: relative; }
.ls-elza-v232-shell {
    position: relative;
    overflow: visible;
    border: 1px solid rgba(136,145,158,.9);
    border-radius: 23px;
    background: #303033;
    box-shadow: inset 0 1px 0 rgba(255,255,255,.035);
}
.ls-elza-v232-shell .ls-elza-input-row {
    display: block;
    padding: 13px 14px 4px;
}
.ls-elza-v232-shell .ls-elza-input {
    width: 100% !important;
    min-height: 54px !important;
    max-height: 160px !important;
    padding: 0 !important;
    border: 0 !important;
    outline: 0 !important;
    resize: vertical;
    background: transparent !important;
    color: #f1f3f4 !important;
    caret-color: #fff;
    box-shadow: none !important;
}
.ls-elza-v232-shell .ls-elza-input::placeholder { color: rgba(238,241,245,.58) !important; }
.ls-elza-v232-actions {
    position: relative;
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 47px;
    padding: 4px 8px 8px;
}
.ls-elza-v232-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: 0 0 36px;
    width: 36px;
    height: 36px;
    padding: 0;
    border: 0;
    border-radius: 50%;
    background: transparent;
    color: #f1f3f4;
    cursor: pointer;
}
.ls-elza-v232-icon:hover { background: rgba(255,255,255,.08); }
.ls-elza-v232-plus { font-size: 29px; font-weight: 300; line-height: 1; }
.ls-elza-v232-spacer { flex: 1 1 auto; min-width: 4px; }
.ls-elza-v232-chip {
    display: none;
    align-items: center;
    min-height: 28px;
    padding: 2px 9px;
    border: 1px solid rgba(124,155,201,.7);
    border-radius: 14px;
    background: rgba(60,86,121,.5);
    color: #eef5ff;
    font-size: 11px;
    font-weight: 700;
}
.ls-elza-v232-chip.active { display: inline-flex; }
.ls-elza-v232-shell #ls-elza-voice {
    position: relative;
    display: inline-flex !important;
    align-items: center;
    justify-content: center;
    flex: 0 0 38px;
    width: 38px !important;
    min-width: 38px !important;
    height: 38px !important;
    min-height: 38px !important;
    padding: 0 !important;
    border: 0 !important;
    border-radius: 50% !important;
    background: transparent !important;
    color: #f1f3f4 !important;
    font-size: 0 !important;
    box-shadow: none !important;
}
.ls-elza-v232-shell #ls-elza-voice::before {
    content: "";
    display: block;
    width: 21px;
    height: 21px;
    background: currentColor;
    -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='black' d='M12 14a3 3 0 0 0 3-3V5a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3Zm-1 4.93V22h2v-3.07A8.001 8.001 0 0 0 20 11h-2a6 6 0 0 1-12 0H4a8.001 8.001 0 0 0 7 7.93Z'/%3E%3C/svg%3E") center / contain no-repeat;
    mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='black' d='M12 14a3 3 0 0 0 3-3V5a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3Zm-1 4.93V22h2v-3.07A8.001 8.001 0 0 0 20 11h-2a6 6 0 0 1-12 0H4a8.001 8.001 0 0 0 7 7.93Z'/%3E%3C/svg%3E") center / contain no-repeat;
}
.ls-elza-v232-shell #ls-elza-voice:hover:not(:disabled) { background: rgba(255,255,255,.08) !important; }
.ls-elza-v232-shell.recording #ls-elza-voice { display: none !important; }
.ls-elza-v232-voice-mode {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    height: 38px;
    padding: 0 14px;
    border: 0;
    border-radius: 19px;
    background: #3f82f7;
    color: #fff;
    cursor: pointer;
    font-size: 14px;
    font-weight: 800;
}
.ls-elza-v232-voice-mode::before { content: "▥"; font-size: 14px; }
.ls-elza-v232-voice-mode:hover { background: #3275e9; }
.ls-elza-v232-shell #ls-elza-send {
    display: inline-flex !important;
    align-items: center;
    justify-content: center;
    flex: 0 0 38px;
    width: 38px !important;
    min-width: 38px !important;
    height: 38px !important;
    min-height: 38px !important;
    padding: 0 !important;
    border: 0 !important;
    border-radius: 50% !important;
    background: #3f82f7 !important;
    color: transparent !important;
    font-size: 0 !important;
    box-shadow: none !important;
}
.ls-elza-v232-shell #ls-elza-send::before {
    content: "↑";
    color: #fff;
    font-size: 25px;
    font-weight: 700;
    line-height: 1;
}
.ls-elza-v232-shell #ls-elza-send:hover:not(:disabled) { background: #3275e9 !important; }
.ls-elza-v232-menu {
    position: absolute;
    left: 7px;
    bottom: 50px;
    z-index: 30;
    display: none;
    min-width: 210px;
    padding: 7px;
    border: 1px solid rgba(130,142,158,.78);
    border-radius: 14px;
    background: #303033;
    box-shadow: 0 14px 36px rgba(0,0,0,.38);
}
.ls-elza-v232-menu.open { display: grid; gap: 4px; }
.ls-elza-v232-menu .ls-elza-mode-btn {
    width: 100% !important;
    height: auto !important;
    min-height: 36px !important;
    justify-content: flex-start !important;
    padding: 7px 10px !important;
    border: 0 !important;
    border-radius: 9px !important;
    background: transparent !important;
    color: transparent !important;
    font-size: 0 !important;
    box-shadow: none !important;
}
.ls-elza-v232-menu .ls-elza-mode-btn:hover:not(:disabled) { background: rgba(255,255,255,.08) !important; }
.ls-elza-v232-menu .ls-elza-mode-btn[aria-pressed="true"] { background: rgba(63,130,247,.28) !important; }
.ls-elza-v232-menu .ls-elza-mode-btn::after { color: #fff; font-size: 13px; font-weight: 700; }
.ls-elza-v232-menu #ls-elza-ux-mode::after { content: "UX pārbaude"; }
.ls-elza-v232-menu #ls-elza-test-mode::after { content: "Testēt funkciju"; }
.ls-elza-v232-menu #ls-elza-track-mode::after { content: "Track analīze"; }
.ls-elza-v232-menu #ls-elza-code-mode::after { content: "Koda analīze"; }
.ls-elza-mode-row.ls-elza-v232-source-row { display: none !important; }
.ls-elza-v232-recording {
    display: none;
    align-items: center;
    gap: 8px;
    flex: 1 1 auto;
    min-width: 0;
}
.ls-elza-v232-shell.recording .ls-elza-v232-recording { display: flex; }
.ls-elza-v232-shell.recording .ls-elza-input-row,
.ls-elza-v232-shell.recording .ls-elza-v232-plus,
.ls-elza-v232-shell.recording .ls-elza-v232-chip,
.ls-elza-v232-shell.recording .ls-elza-v232-spacer,
.ls-elza-v232-shell.recording .ls-elza-v232-voice-mode { display: none !important; }
.ls-elza-v232-cancel,
.ls-elza-v232-stop {
    flex: 0 0 36px;
    width: 36px;
    height: 36px;
    padding: 0;
    border: 0;
    border-radius: 50%;
    color: #f1f3f4;
    cursor: pointer;
}
.ls-elza-v232-cancel { background: transparent; font-size: 26px; }
.ls-elza-v232-stop { background: rgba(255,255,255,.09); font-size: 14px; }
.ls-elza-v232-cancel:hover,
.ls-elza-v232-stop:hover { background: rgba(255,255,255,.15); }
.ls-elza-v232-wave {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 2px;
    flex: 1 1 auto;
    min-width: 100px;
    height: 32px;
    overflow: hidden;
}
.ls-elza-v232-wave > span {
    display: block;
    width: 3px;
    height: 3px;
    border-radius: 2px;
    background: rgba(241,243,244,.9);
    opacity: .42;
    transform-origin: center;
}
.ls-elza-v232-shell.recording .ls-elza-send { display: inline-flex !important; }
</style>
