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

def _ls_migrate_legacy_runtime_file(file_name, destination_dir):
    """Atomically move one legacy root file when the structured target is free."""
    source = BASE_DIR / file_name
    target = Path(destination_dir) / file_name
    if source == target or not source.is_file() or target.exists():
        return False
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, target)
        return True
    except OSError:
        return False

ACTIVE_HTTP_SERVER = None

def sanitize_ls_error_data(value, key_name=""):
    """Return a JSON-safe copy with authentication data removed."""
    if key_name and LS_SENSITIVE_KEY_PATTERN.search(str(key_name)):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            str(key): sanitize_ls_error_data(item, str(key))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [sanitize_ls_error_data(item) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    text = str(value)
    for pattern in LS_SENSITIVE_TEXT_PATTERNS:
        text = pattern.sub(lambda match: match.group(1) + "[REDACTED]", text)
    return text

def write_ls_error_log(
    area,
    action,
    error,
    context=None,
    traceback_text="",
    log_path=None,
    previous_path=None,
    max_bytes=None,
):
    """Append one sanitized JSONL error record. Logging must never stop LS."""
    try:
        target_path = Path(log_path or LS_ERROR_LOG_PATH)
        rotated_path = Path(previous_path or LS_ERROR_LOG_PREVIOUS_PATH)
        size_limit = int(max_bytes or LS_ERROR_LOG_MAX_BYTES)
        error_type = type(error).__name__ if isinstance(error, BaseException) else "Error"
        message = str(error or "Unknown error")
        record = sanitize_ls_error_data({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "app_version": APP_VERSION,
            "area": str(area or "unknown"),
            "action": str(action or "unknown"),
            "error_type": error_type,
            "message": message,
            "context": context if isinstance(context, dict) else {"detail": context} if context else {},
            "traceback": str(traceback_text or ""),
        })
        encoded = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        with LS_ERROR_LOG_LOCK:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            current_size = target_path.stat().st_size if target_path.exists() else 0
            if current_size + len(encoded) > size_limit and target_path.exists():
                try:
                    if rotated_path.exists():
                        rotated_path.unlink()
                    os.replace(target_path, rotated_path)
                except Exception:
                    pass
            with target_path.open("ab") as log_file:
                log_file.write(encoded)
                log_file.flush()
    except Exception:
        return False
    return True

def log_ls_exception(area, action, exc, context=None, include_traceback=True):
    """Route Upgrade failures to their own journal; keep other LS errors separate."""
    tb_text = ""
    if include_traceback:
        tb_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    is_upgrade_error = str(area or "").strip().casefold() == "upgrade"
    return write_ls_error_log(
        area=area,
        action=action,
        error=exc,
        context=context or {},
        traceback_text=tb_text,
        log_path=LS_UPGRADE_ERROR_LOG_PATH if is_upgrade_error else None,
        previous_path=LS_UPGRADE_ERROR_LOG_PREVIOUS_PATH if is_upgrade_error else None,
        max_bytes=LS_UPGRADE_LOG_MAX_BYTES if is_upgrade_error else None,
    )

def ensure_ls_upgrade_log_files():
    """Create the two dedicated Upgrade journals once without touching existing timestamps."""
    for target_path in (LS_UPGRADE_AUDIT_LOG_PATH, LS_UPGRADE_ERROR_LOG_PATH):
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if not target_path.exists():
                with target_path.open("xb"):
                    pass
        except FileExistsError:
            pass
        except Exception:
            # Log initialization must never prevent LS from starting.
            pass

def get_default_help_text():
    return """SUNO FINDER — ĪSA PALĪDZĪBA

1. Galvenā doma

LocalSunoDb rāda lokālu Suno dziesmu katalogu no LS datubāzes.
Tas nav pats Suno konts. Dažas darbības maina tikai LS datubāzi vai lokālos failus.

2. Nosaukums

Klikšķis uz dziesmas nosaukuma atver ierakstu Suno lapā.

Ja redzams skaitlis iekavās, piemēram:
Dziesma (2)

tas nozīmē, ka tajā pašā workspace ir vairāki ieraksti ar vienādu nosaukumu.
Skaitlis ir tikai ekrāna marķieris. DB nosaukums netiek mainīts.

3. BPM un modelis pie nosaukuma

BPM parāda tempu, ja tas ir zināms.

v5.5 — apstiprināts jaunākais modelis.
v5.5? — pēc datuma iespējams v5.5, bet nav droši apstiprināts metadatos.
v5 / v4.5 / v4 / v3.5 — vecāki modeļi, galvenokārt šķirošanai un izziņai.
— — modelis nav zināms.

4. Like

Dzeltens īkšķis nozīmē Like.
Tikai īkšķa kontūra nozīmē nav Like.

Like maiņa notiek LS datubāzē. Tā nav obligāti sinhrona ar Suno serveri.

5. Compare

Compare parādās, ja šim Suno ierakstam LS datubāzē ir piesaistīts lokāls WAV fails.
Compare atver divus atskaņotājus: Suno audio un lokālo WAV.

6. Row menu ⋮

Open in Suno — atver Suno ierakstu.
Copy Track ID — nokopē Suno Track ID.
Add local audio path — piesaista svaigi lejupielādētu WAV/MP3 failu šim ierakstam LS datubāzē.
Delete local variant — pārvieto visu numurēto varianta mapi (arī Stems) uz LS Backup, izveido DB backup un noņem šī varianta DB saites.
Delete local audio — vecais viena piesaistītā faila dzēšanas režīms nestandarta / vecajām mapēm.
Hide from Finder — paslēpj ierakstu LS sarakstā. Tas nedzēš dziesmu no Suno.

7. Hide from Finder

Hide paslēpj ierakstu tikai LocalSunoDb skatā.
Tas nedzēš Suno dziesmu un nedzēš lokālo failu.

8. Delete local audio

Delete local audio nedzēš failu neatgriezeniski.
Fails tiek pārvietots uz:
E:\\LocalSunoDb\\Backup\\deleted_local_audio

un saite tiek izņemta no LS datubāzes.

9. Refresh DB

Refresh DB pārlasa Suno / lokālos metadatus.
Tas var aizņemt vairākas minūtes.

10. Stems un lokālie audio faili

LS WAV lejupielādes struktūra:
E:\\Audio-Lib-NEW\\Song|Instrumental\\Dziesmas nosaukums\\1,2,3...\\Dziesmas nosaukums.wav
Katrā varianta mapē tiek izveidota arī Stems apakšmape.

LocalSunoDb pamata saraksts rāda Suno dziesmas no tracks tabulas.
Lokālie Stem faili tiek glabāti atsevišķi local_audio_files tabulā.

Kind = Stem ir Suno metadatu rinda, nevis pilnvērtīga atsevišķa dziesma.
Ikdienas All sarakstā Stem metadata rindas vairs netiek rādītas.

Lai atrastu dziesmas, kurām LS datubāzē ir piesaistīti lokālie Stem faili, Kind sarakstā izvēlies:
Has Stems

Lai turpinātu kārtošanu un atrastu Stem metadata rindas, kuras vēl nav piesaistītas pilnajai dziesmai, izvēlies:
Unlinked Stems

Ierakstiem ar lokāliem Stems pie nosaukuma redzama marciņa Stems N, un Play poga ir zaļa.
Atverot zaļo Play, var klausīties Suno audio un lokālos Stem celiņus.

11. Šķirošana

Klikšķis uz kolonnas nosaukuma šķiro sarakstu.
Atkārtots klikšķis maina virzienu ASC/DESC.
F5 / Ctrl+R saglabā pašreizējo Suno Database vietu: pēc pārlādes LS atgriežas pie tās pašas Track ID rindas un tā paša ekrāna nobīdes.

12. Flags and Tags panelis

Flags and Tags atver vienotu marķēšanas paneli izvēlētajai dziesmai.

Panelī var:
- ieslēgt vai izslēgt piecus neatkarīgos LS Flags;
- pievienot jaunu tagu un uzreiz piešķirt to dziesmai;
- meklēt tagus;
- šķirot A–Z / Z–A;
- piespraust biežāk lietotos tagus augšpusē;
- ar vienu klikšķi pievienot vai noņemt tagu konkrētajai dziesmai;
- dzēst tagu no kopējā saraksta.

Aktīvās atlases joslas poga + Add filter atver to pašu paneli režīmā
Filter Library. Šis režīms nemaina DB: tas atlasa dziesmas pēc konkrētiem
Flags un #tagiem. Ja izvēlēti vairāki nosacījumi, dziesmai jāatbilst tiem
visiem (AND).

Tos pašus nosacījumus var rakstīt Ctrl+F laukā kopā ar parasto tekstu:
- 0+* = jebkurš no pieciem LS Flags;
- 1+* ... 5+* = konkrētais Flag;
- #tags = konkrētais lietotāja tags.
Piemērs: Upe 2+* #jazz atlasa ierakstus, kuros ir vārds Upe, otrais Flag
un tags #jazz. Visi ievadītie nosacījumi darbojas kopā ar AND un pēc
piemērošanas ir redzami aktīvo filtru joslā.

Workspace un Category sarakstos parasts klikšķis izvēlas vienu vērtību.
Ctrl+klikšķis pievieno vai noņem vienu vērtību no pašreizējās atlases.
Vairākas Workspace vai Category vērtības savā grupā darbojas ar OR, bet
atšķirīgas filtru grupas savā starpā darbojas ar AND.

Ja Workspace vai Category sarakstā atlasītas vismaz divas vērtības, var
izvēlēties AND by Local family. Tad LS atrod tikai tās apstiprinātās Local
families, kurām ir vismaz viens precīzi piesaistīts Track ID katrā izvēlētajā
Workspace vai Category. Rezultātu sarakstā paliek izvēlēto grupu ieraksti no
šīm ģimenēm. OR atjauno parasto jebkuras izvēlētās vērtības atlasi.

Local family saraksts rāda tikai pastāvīgi apstiprinātās Track ID ģimenes
no suno_local_family_map.json. Mapju nosaukumi bez apstiprinātas Track ID
piesaistes šajā filtrā netiek izmantoti. Parasts klikšķis uz Local family
atver tīru ģimenes fokusa skatu un noņem citus filtrus, saglabājot tikai
kārtošanu. Ctrl+klikšķis ģimeni apzināti kombinē ar pašreizējiem filtriem
vai pievieno/noņem citas Local families.

13. Saved views

Save view saglabā pašreizējo Suno Database filtru un šķirošanas kombināciju
LS iestatījumos. Dziesmu DB netiek mainīta. Views izvēlnē saglabāto skatu var
atvērt ar vienu klikšķi, pārdēvēt vai dzēst. Atverot saglabātu skatu, tas
aizstāj pašreizējo atlasi, nevis pievienojas tai.

14. LS Elza atlases komandas

Elza lokāli atpazīst skaidras komandas, piemēram, “Parādi Liked dziesmas bez
lokālā audio”, izveido read-only priekšskatījumu un piedāvā Atvērt atlasi LS
vai Saglabāt kā View. Var kombinēt Liked vai Has Stems ar lokālā audio,
Song/Instrumental, 0+*…5+*, precīziem #tagiem, citētu Workspace, Local family
vai nosaukuma tekstu. Vienkāršajām atlases komandām OpenAI API netiek izmantota.

Globāla taga dzēšana vispirms izveido DB un tagu saraksta Backup un pēc tam
noņem šo pašu #tag marķējumu arī no visiem track_ui.user_tags ierakstiem.

#tagu katalogs:
E:\\LocalSunoDb\\Data\\localsunodb_tags.txt
"""

def get_help_source():
    """Prefer Help_LocalSunoDb.md; keep TXT and built-in Help as fallbacks."""
    candidates = [
        (HELP_MARKDOWN_PATH, "markdown"),
        (HELP_LEGACY_TEXT_PATH, "text"),
    ]

    for path_obj, source_format in candidates:
        try:
            if path_obj.exists() and path_obj.is_file():
                source_text = path_obj.read_text(
                    encoding="utf-8",
                    errors="replace",
                ).strip()
                if source_text:
                    return source_text, source_format, str(path_obj)
        except Exception:
            pass

    return get_default_help_text(), "text", "built-in Help"

def get_help_text():
    return get_help_source()[0]

def _help_slugify(value, used):
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    slug = re.sub(r"[^\w]+", "-", value.lower(), flags=re.UNICODE).strip("-_")
    slug = slug or "section"

    base = slug
    number = 2
    while slug in used:
        slug = f"{base}-{number}"
        number += 1

    used.add(slug)
    return slug

def _help_inline(value):
    """Safe inline Markdown: code, bold and italic; raw HTML is escaped."""
    source = str(value or "")
    protected = {}

    def save_code(match):
        token = f"@@LSHELP{len(protected)}@@"
        protected[token] = (
            "<code>"
            + html.escape(match.group(1), quote=False)
            + "</code>"
        )
        return token

    source = re.sub(r"`([^`\n]+)`", save_code, source)
    result = html.escape(source, quote=False)
    result = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", result)
    result = re.sub(
        r"(?<!\*)\*([^*\n]+)\*(?!\*)",
        r"<em>\1</em>",
        result,
    )

    for token, code_html in protected.items():
        result = result.replace(token, code_html)

    return result

def _help_cells(line):
    value = str(line or "").strip()
    if value.startswith("|"):
        value = value[1:]
    if value.endswith("|"):
        value = value[:-1]
    return [cell.strip() for cell in value.split("|")]

def _help_table_rule(line):
    cells = _help_cells(line)
    return bool(cells) and all(
        re.fullmatch(r":?-{3,}:?", cell.replace(" ", ""))
        for cell in cells
    )

def render_help_markdown(markdown_text):
    """Render the local Help Markdown without third-party packages."""
    lines = str(markdown_text or "").replace("\r\n", "\n").split("\n")
    output = []
    toc = []
    used_slugs = set()
    paragraph = []
    first_h1 = True

    def flush_paragraph():
        nonlocal paragraph
        if not paragraph:
            return

        parts = []
        for item_index, item in enumerate(paragraph):
            hard_break = item.endswith("  ")
            parts.append(_help_inline(item.rstrip()))
            if item_index < len(paragraph) - 1:
                parts.append("<br>" if hard_break else " ")

        output.append("<p>" + "".join(parts) + "</p>")
        paragraph = []

    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            index += 1
            continue

        if stripped.startswith("```"):
            flush_paragraph()
            language = stripped[3:].strip()
            code_lines = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            language_attr = (
                f' class="language-{html.escape(language, quote=True)}"'
                if language
                else ""
            )
            output.append(
                f"<pre><code{language_attr}>"
                + html.escape("\n".join(code_lines), quote=False)
                + "</code></pre>"
            )
            continue

        if (
            "|" in line
            and index + 1 < len(lines)
            and _help_table_rule(lines[index + 1])
        ):
            flush_paragraph()
            headers = _help_cells(line)
            index += 2
            rows = []

            while index < len(lines):
                candidate = lines[index]
                if not candidate.strip() or "|" not in candidate:
                    break
                rows.append(_help_cells(candidate))
                index += 1

            pieces = ['<div class="help-table"><table><thead><tr>']
            pieces.extend(
                "<th>" + _help_inline(cell) + "</th>"
                for cell in headers
            )
            pieces.append("</tr></thead><tbody>")
            for row in rows:
                row = row + [""] * max(0, len(headers) - len(row))
                pieces.append("<tr>")
                pieces.extend(
                    "<td>" + _help_inline(cell) + "</td>"
                    for cell in row[:len(headers)]
                )
                pieces.append("</tr>")
            pieces.append("</tbody></table></div>")
            output.append("".join(pieces))
            continue

        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            heading_id = _help_slugify(title, used_slugs)
            title_class = ""

            if level == 1 and first_h1:
                title_class = ' class="help-document-title"'
                first_h1 = False

            output.append(
                f'<h{level} id="{heading_id}"{title_class}>'
                + _help_inline(title)
                + f'<a class="heading-link" href="#{heading_id}">#</a>'
                + f"</h{level}>"
            )

            if level == 2:
                toc.append(
                    f'<a href="#{heading_id}">'
                    + html.escape(title, quote=False)
                    + "</a>"
                )

            index += 1
            continue

        if re.fullmatch(r"\s*(---+|\*\*\*+|___+)\s*", line):
            flush_paragraph()
            output.append("<hr>")
            index += 1
            continue

        if stripped.startswith(">"):
            flush_paragraph()
            quote_lines = []
            while index < len(lines) and lines[index].lstrip().startswith(">"):
                quote_line = lines[index].lstrip()[1:]
                quote_lines.append(quote_line[1:] if quote_line.startswith(" ") else quote_line)
                index += 1
            output.append(
                '<blockquote><span class="quote-star">★</span><div>'
                + "<br>".join(_help_inline(item) for item in quote_lines)
                + "</div></blockquote>"
            )
            continue

        unordered = re.match(r"^\s*[-+*]\s+(.+)$", line)
        if unordered:
            flush_paragraph()
            items = []
            while index < len(lines):
                match = re.match(r"^\s*[-+*]\s+(.+)$", lines[index])
                if not match:
                    break
                items.append(match.group(1))
                index += 1
            output.append(
                "<ul>"
                + "".join("<li>" + _help_inline(item) + "</li>" for item in items)
                + "</ul>"
            )
            continue

        ordered = re.match(r"^\s*\d+[.)]\s+(.+)$", line)
        if ordered:
            flush_paragraph()
            items = []
            while index < len(lines):
                match = re.match(r"^\s*\d+[.)]\s+(.+)$", lines[index])
                if not match:
                    break
                items.append(match.group(1))
                index += 1
            output.append(
                "<ol>"
                + "".join("<li>" + _help_inline(item) + "</li>" for item in items)
                + "</ol>"
            )
            continue

        paragraph.append(line)
        index += 1

    flush_paragraph()
    return "\n".join(output), "".join(toc)

def find_profile_image_path():
    for path in PROFILE_IMAGE_CANDIDATES:
        if path.exists() and path.is_file():
            return path
    accepted_stems = {"suno_profile", "profile", "avatar"}
    accepted_suffixes = {".png", ".jpg", ".jpeg", ".webp"}
    try:
        for path in BASE_DIR.iterdir():
            if (
                path.is_file()
                and path.stem.casefold() in accepted_stems
                and path.suffix.casefold() in accepted_suffixes
            ):
                return path
    except OSError:
        pass
    return None

def get_settings():
    default = {
        "audio_library_root_folder": r"E:\Audio-Lib-NEW",
        "stem_root_folder": r"E:\Audio-Lib-NEW",
        "ls_update_check_interval_seconds": 10,
        "autoplay_list": False,
        "ls_elza_background_opacity": 50,
        "audio_output_speakers_id": "",
        "audio_output_headphones_id": "",
        "local_family_title": "",
        "suno_api_token": "",
        "suno_api_token_updated_at": "",
        "suno_api_token_source": "",
        "suno_api_token_invalid_at": "",
        "suno_device_id": "",
        "suno_credits_remaining": None,
        "suno_credits_updated_at": "",
        "saved_views": [],
    }

    try:
        if SETTINGS_PATH.exists():
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8", errors="replace"))
            if isinstance(data, dict):
                default.update({k: v for k, v in data.items() if isinstance(k, str)})
    except Exception as exc:
        log_ls_exception(
            "settings",
            "read_settings",
            exc,
            context={"path": str(SETTINGS_PATH)},
            include_traceback=False,
        )

    return default

def save_settings(settings):
    current = get_settings()
    current.update(settings or {})
    SETTINGS_PATH.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    return current

def normalize_last_view_url(value):
    """Keep only safe LocalSunoDb top-level page URLs that may be restored."""
    text = str(value or "").strip()
    if not text:
        return "/"

    parsed = urllib.parse.urlsplit(text)
    path = parsed.path or "/"
    if path not in ("/", "/downloader"):
        return "/"

    result = path
    if parsed.query:
        result += "?" + parsed.query
    return result

def get_view_section(view_url):
    path = urllib.parse.urlsplit(normalize_last_view_url(view_url)).path or "/"
    if path == "/downloader":
        return "downloader"
    return "suno"

def _load_last_view_state():
    data = {}
    try:
        if LAST_VIEW_STATE_PATH.exists():
            loaded = json.loads(LAST_VIEW_STATE_PATH.read_text(encoding="utf-8", errors="replace"))
            if isinstance(loaded, dict):
                data = loaded
    except Exception:
        data = {}

    section_views = data.get("section_views")
    if not isinstance(section_views, dict):
        section_views = {}

    # Backward compatibility with v4.66-v4.83: migrate the one remembered URL
    # into the matching section without discarding it.
    legacy_url = normalize_last_view_url(data.get("view_url") or "/")
    legacy_section = get_view_section(legacy_url)
    if legacy_url and legacy_section not in section_views:
        section_views[legacy_section] = legacy_url

    clean_views = {}
    for section, default_url in SECTION_VIEW_DEFAULTS.items():
        candidate = normalize_last_view_url(section_views.get(section) or default_url)
        if get_view_section(candidate) != section:
            candidate = default_url
        clean_views[section] = candidate

    last_section = str(data.get("last_section") or legacy_section or "suno").strip().lower()
    if last_section not in SECTION_VIEW_DEFAULTS:
        last_section = "suno"

    return {
        "section_views": clean_views,
        "last_section": last_section,
        "view_url": clean_views[last_section],
        "saved_at": str(data.get("saved_at") or ""),
        "saved_by_version": str(data.get("saved_by_version") or ""),
    }

def _save_last_view_state(state):
    LAST_VIEW_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = LAST_VIEW_STATE_PATH.with_suffix(LAST_VIEW_STATE_PATH.suffix + ".tmp")
    temp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(LAST_VIEW_STATE_PATH)

def save_section_view_url(section, view_url, make_last=True):
    section = str(section or "").strip().lower()
    if section not in SECTION_VIEW_DEFAULTS:
        section = get_view_section(view_url)

    clean_url = normalize_last_view_url(view_url)
    if get_view_section(clean_url) != section:
        clean_url = SECTION_VIEW_DEFAULTS[section]

    state = _load_last_view_state()
    state["section_views"][section] = clean_url
    if make_last:
        state["last_section"] = section
    state["view_url"] = state["section_views"][state["last_section"]]
    state["saved_at"] = now_iso_local()
    state["saved_by_version"] = APP_VERSION
    _save_last_view_state(state)
    return clean_url

def save_last_view_url(view_url):
    """Persist the exact URL independently for Suno, Local and Downloader."""
    clean_url = normalize_last_view_url(view_url)
    return save_section_view_url(get_view_section(clean_url), clean_url, make_last=True)

def get_section_view_url(section):
    section = str(section or "").strip().lower()
    if section not in SECTION_VIEW_DEFAULTS:
        section = "suno"
    state = _load_last_view_state()
    return state["section_views"].get(section) or SECTION_VIEW_DEFAULTS[section]

def get_last_view_url():
    state = _load_last_view_state()
    section = state.get("last_section") or "suno"
    return state["section_views"].get(section) or SECTION_VIEW_DEFAULTS[section]

def get_audio_library_root_folder():
    settings = get_settings()
    return str(
        settings.get("audio_library_root_folder")
        or settings.get("stem_root_folder")
        or r"E:\Audio-Lib-NEW"
    )

def set_audio_library_root_folder(folder_path):
    folder_path = urllib.parse.unquote(str(folder_path or "")).strip().strip('"')
    if not folder_path:
        return False, "Missing audio library root folder"
    path_obj = Path(folder_path)
    if not path_obj.exists() or not path_obj.is_dir():
        return False, "Folder not found"
    save_settings({"audio_library_root_folder": str(path_obj)})
    return True, str(path_obj)

def get_stem_root_folder():
    return str(get_settings().get("stem_root_folder") or get_audio_library_root_folder())

def get_ls_update_check_interval_setting():
    try:
        seconds = int(str(
            get_settings().get("ls_update_check_interval_seconds", 10)
        ).strip())
    except Exception:
        seconds = 10
    if seconds <= 0:
        return 0
    return max(5, min(3600, seconds))

def set_ls_update_check_interval_setting(value):
    try:
        seconds = int(str(value or "0").strip())
    except Exception:
        return False, "Invalid update check interval"
    if seconds != 0 and not 5 <= seconds <= 3600:
        return False, "Use 0 (off) or 5–3600 seconds"
    save_settings({"ls_update_check_interval_seconds": seconds})
    return True, str(seconds)

def set_autoplay_list_setting(value):
    enabled = normalize_search_scope_flag(value, False)
    save_settings({"autoplay_list": enabled})
    return True, "1" if enabled else "0"

def get_ls_elza_background_opacity():
    """Return the saved LS Elza surface opacity as an integer percentage."""
    try:
        value = int(get_settings().get("ls_elza_background_opacity", 50))
    except Exception:
        value = 50
    return max(20, min(100, value))

def set_ls_elza_background_opacity(value):
    """Persist LS Elza background opacity without changing text opacity."""
    try:
        opacity = int(round(float(str(value or "50").strip())))
    except Exception:
        return False, "Invalid LS Elza opacity", get_ls_elza_background_opacity()

    opacity = max(20, min(100, opacity))
    save_settings({"ls_elza_background_opacity": opacity})
    return True, f"LS Elza background opacity saved: {opacity}%", opacity

def set_stem_root_folder(folder_path):
    folder_path = urllib.parse.unquote(str(folder_path or "")).strip().strip('"')
    if not folder_path:
        return False, "Missing folder path"
    path_obj = Path(folder_path)
    if not path_obj.exists() or not path_obj.is_dir():
        return False, "Folder not found"
    save_settings({"stem_root_folder": str(path_obj)})
    return True, str(path_obj)



def run_refresh_db():
    if not REFRESH_SCRIPT.exists():
        return False, f"Missing refresh script: {REFRESH_SCRIPT}"

    try:
        result = subprocess.run(
            [sys.executable, str(REFRESH_SCRIPT)],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return False, "refresh_db.py timeout"
    except Exception as e:
        return False, str(e)

    output_parts = []

    if result.stdout:
        output_parts.append(result.stdout.strip())

    if result.stderr:
        output_parts.append(result.stderr.strip())

    output = "\n\n".join(output_parts).strip()

    if result.returncode != 0:
        return False, output or "refresh_db.py failed"

    print()
    print("Refresh DB output:")
    print("-" * 50)
    print(output)

    return True, output

def get_latest_refresh_summary(max_chars=3500):
    """Read the latest refresh summary written by refresh_db.py."""
    if not REFRESH_SUMMARY_PATH.exists():
        return ""
    try:
        text = REFRESH_SUMMARY_PATH.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""
    if not text:
        return ""
    marker = "\n--------------------------------------------------------------------------------\n"
    if marker in text:
        parts = text.split(marker)
        latest = "--------------------------------------------------------------------------------\n" + parts[-1].strip()
    else:
        latest = text[-max_chars:]
    if len(latest) > max_chars:
        latest = latest[-max_chars:]
    return latest.strip()

def esc(value):
    return html.escape(str(value or ""))

def like_thumb_svg():
    return (
        '<svg class="ls-like-thumb" viewBox="0 0 64 64" aria-hidden="true" focusable="false">'
        '<path class="ls-like-thumb-path" d="M23 58 H10 C7.8 58 6 56.2 6 54 V30 C6 27.8 7.8 26 10 26 H23 '
        'V58 Z M23 26 C28 23 32 16 33 8 C33.3 5.6 35.2 4 37.4 4 C41 4 44 7.1 43.5 11 '
        'L42.2 22 H54 C58.1 22 61.2 25.7 60.5 29.8 L56.8 51.8 C56.2 55.4 53.1 58 49.5 58 H23 Z"/>'
        '</svg>'
    )

def lv_sort_key(value):
    """Simple Latvian-friendly sort key: ignore accents/case for A-Z ordering."""
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text

def make_suno_url(track_id):
    if not track_id:
        return ""
    return f"https://suno.com/song/{track_id}"

def format_duration(value):
    if value is None or value == "":
        return ""

    try:
        seconds = float(value)
    except ValueError:
        return str(value)

    minutes = int(seconds // 60)
    rest = int(seconds % 60)
    return f"{minutes}:{rest:02d}"

def duration_sort_value(value):
    """Return duration in seconds for sorting. Accepts seconds, m:ss, h:mm:ss."""
    if value is None or value == "":
        return 0

    text = str(value).strip()

    try:
        return float(text)
    except (TypeError, ValueError):
        pass

    parts = text.split(":")
    try:
        if len(parts) == 2:
            minutes = int(parts[0])
            seconds = float(parts[1])
            return minutes * 60 + seconds
        if len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
    except (TypeError, ValueError):
        return 0

    return 0

def parse_created_at(value):
    if not value:
        return None

    text = str(value).strip()

    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        dt = datetime.fromisoformat(text)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone()
    except ValueError:
        return None

def format_created_at(value):
    dt = parse_created_at(value)

    if not dt:
        return str(value or "")

    month = MONTHS.get(dt.month, "")
    return f"{dt.day:02d}. {month} {dt.year}. {dt.hour:02d}:{dt.minute:02d}"

def created_sort_value(value):
    dt = parse_created_at(value)

    if not dt:
        return 0

    return int(dt.timestamp())

def shorten_text(value, max_length=120):
    text = str(value or "").strip()

    if len(text) <= max_length:
        return text

    return text[:max_length - 1] + "…"

def selected_attr(current, value):
    if current == value:
        return "selected"
    return ""

def format_like(value):
    text = str(value or "").strip().lower()

    if text == "true":
        return "👍"

    if text == "false":
        return ""

    return "?"

def like_sort_value(value):
    text = str(value or "").strip().lower()

    if text == "true":
        return "yes"

    if text == "false":
        return "no"

    return "unknown"

def waveform_cache_name(track_id, audio_url):
    source = track_id or audio_url or "unknown"
    digest = hashlib.sha1(source.encode("utf-8", errors="ignore")).hexdigest()
    return f"{digest}.png"

def normalize_main_category_confidence(value):
    text = str(value or "").strip().lower()
    if text in ["strong", "3"]:
        return "strong"
    if text in ["medium", "2"]:
        return "medium"
    if text in ["weak", "1"]:
        return "weak"
    if text in ["special", "0"]:
        return "special"
    return "weak"

def main_category_badge_class(category, confidence_label):
    cat = str(category or "").strip().lower()
    conf = normalize_main_category_confidence(confidence_label)
    if cat == "instrumental":
        return f"main-category-badge main-category-instrumental main-category-confidence-{conf}"
    if cat == "song":
        return f"main-category-badge main-category-song main-category-confidence-{conf}"
    return "main-category-badge main-category-unknown main-category-confidence-weak"

def detect_suno_ui_badges(title="", kind="", style="", prompt="", lyrics=""):
    """Small Suno-style UI badges. These are visual hints only; they do not change DB data."""
    title_low = str(title or "").lower()
    kind_low = str(kind or "").lower()
    haystack = " ".join([
        str(title or ""),
        str(kind or ""),
        str(style or ""),
        str(prompt or ""),
        str(lyrics or ""),
    ]).lower()

    badges = []

    if kind_low == "song":
        badges.append(("Song", "song"))

    if kind_low == "instrumental":
        badges.append(("Instrumental", "instrumental"))

    if kind_low in ["upload", "uploads"]:
        badges.append(("Upload", "upload"))

    if kind_low == "cover" or re.search(r"(^|[\s\(\[-])cover([\s\)\]-]|$)", title_low):
        badges.append(("Cover", "cover"))

    if kind_low == "mashup" or "mashup" in haystack or "mash-up" in haystack:
        badges.append(("Mashup", "mashup"))

    if kind_low == "extend" or re.search(r"(^|[\s\(\[-])extend(ed)?([\s\)\]-]|$)", haystack):
        badges.append(("Extend", "extend"))

    return badges

def get_last_imported_suno_ids():
    value = get_settings().get("last_imported_suno_ids") or []
    if isinstance(value, str):
        value = [x.strip() for x in value.replace(",", "\n").splitlines() if x.strip()]
    if not isinstance(value, list):
        return []
    result = []
    seen = set()
    for item in value:
        tid = str(item or "").strip()
        if tid and tid.lower() not in seen:
            result.append(tid)
            seen.add(tid.lower())
    return result

def set_last_imported_suno_ids(ids):
    result = []
    seen = set()
    for item in ids or []:
        tid = str(item or "").strip()
        if tid and tid.lower() not in seen:
            result.append(tid)
            seen.add(tid.lower())
    save_settings({
        "last_imported_suno_ids": result,
        "last_imported_suno_at": now_iso_local(),
    })

def get_ignored_suno_tracklist_ids():
    value = get_settings().get("ignored_suno_tracklist_ids") or []
    if isinstance(value, str):
        value = [x.strip() for x in value.replace(",", "\n").splitlines() if x.strip()]
    if not isinstance(value, list):
        return []
    result = []
    seen = set()
    for item in value:
        tid = str(item or "").strip()
        if tid and tid.lower() not in seen:
            result.append(tid)
            seen.add(tid.lower())
    return result

def add_ignored_suno_tracklist_ids(ids):
    old_ids = get_ignored_suno_tracklist_ids()
    result = []
    seen = set()
    for item in list(old_ids) + list(ids or []):
        tid = str(item or "").strip()
        if tid and tid.lower() not in seen:
            result.append(tid)
            seen.add(tid.lower())
    save_settings({
        "ignored_suno_tracklist_ids": result,
        "ignored_suno_tracklist_updated_at": now_iso_local(),
    })
    return result

def remove_ignored_suno_tracklist_ids(ids):
    remove_set = {
        str(item or "").strip().lower()
        for item in ids or []
        if str(item or "").strip()
    }
    old_ids = get_ignored_suno_tracklist_ids()
    result = [tid for tid in old_ids if tid.lower() not in remove_set]
    save_settings({
        "ignored_suno_tracklist_ids": result,
        "ignored_suno_tracklist_updated_at": now_iso_local(),
    })
    return result, len(old_ids) - len(result)

def get_ignored_suno_tracklist_summary():
    ids = get_ignored_suno_tracklist_ids()
    return {
        "ok": True,
        "ignored_total": len(ids),
        "ignored_ids": ids,
        "updated_at": get_settings().get("ignored_suno_tracklist_updated_at", ""),
    }

def get_command_line_value(flag_name):
    try:
        index = sys.argv.index(str(flag_name))
    except ValueError:
        return ""
    if index + 1 >= len(sys.argv):
        return ""
    return str(sys.argv[index + 1] or "")


def now_iso_local():
    return datetime.now().isoformat(timespec="seconds")


def normalize_search_scope_flag(value, default=False):
    text = str(value).strip().lower()
    if text in ["1", "true", "yes", "on"]:
        return True
    if text in ["0", "false", "no", "off"]:
        return False
    return bool(default)


def parse_local_iso(value):
    try:
        return datetime.fromisoformat(str(value or "").strip())
    except Exception:
        return None

