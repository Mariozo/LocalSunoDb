# LS Elza - OpenAI consultation service
# Created: 13.jul.2026   07:03
# Modified: 23.aug.2026   07:55
# Purpose: Provide read-only AI consultation and local chat history for LocalSunoDb
# ver. 2.5 - route primary AI execution through Elza Core Contract-v1 facade

# 1.  ------ Imports -----

import base64
import binascii
import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .elza_core import ELZA_CORE_VERSION
from .elza_core.api import ElzaCore
from .elza_core.tools import ToolResult
from .host_paths import (
    DATA_DIR,
    HOST_ROOT,
    LEGACY_DATA_DIR,
    LEGACY_LOGS_DIR,
    LEGACY_PACKAGE_DIR,
    LOGS_DIR,
    copy_legacy_runtime_file,
    ensure_runtime_dirs,
)
from .ls_adapter.runtime_bridge import (
    INVALID_TOOL_ARGUMENTS_KEY,
    OpenAIResponsesProvider,
    LSReadOnlyToolRuntime,
    build_core_context_snapshot,
    build_core_request,
    validate_openai_tool_definitions,
)
from .selection_intent import (
    SELECTION_TOOL_NAME,
    extract_selection_request,
    get_selection_tool_definition,
    normalize_selection_request,
)

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from .readonly import LSElzaReadOnlyError
    from .readonly import get_readonly_tool_definitions
    from .readonly import run_readonly_action
    LS_ELZA_READONLY_IMPORT_ERROR = ""
except Exception as ls_elza_readonly_import_error:
    LSElzaReadOnlyError = None
    get_readonly_tool_definitions = None
    run_readonly_action = None
    LS_ELZA_READONLY_IMPORT_ERROR = str(ls_elza_readonly_import_error)

try:
    from .code_reader import LSElzaCodeReadOnlyError
    from .code_reader import configure_app_source as configure_code_reader_source
    from .code_reader import get_code_tool_definitions
    from .code_reader import run_code_action
    LS_ELZA_CODE_READER_IMPORT_ERROR = ""
except Exception as ls_elza_code_reader_import_error:
    LSElzaCodeReadOnlyError = None
    configure_code_reader_source = None
    get_code_tool_definitions = None
    run_code_action = None
    LS_ELZA_CODE_READER_IMPORT_ERROR = str(ls_elza_code_reader_import_error)


# 2.  ------ Paths and settings -----

BASE_DIR = HOST_ROOT
LS_UPDATE_PROBE_MODE = (
    os.environ.get("LS_UPDATE_PROBE") == "1"
    or "--ls-update-probe" in os.sys.argv
)
ensure_runtime_dirs(LS_UPDATE_PROBE_MODE)

if not LS_UPDATE_PROBE_MODE:
    copy_legacy_runtime_file(
        "ls_elza_history.json",
        DATA_DIR,
        (LEGACY_PACKAGE_DIR / "Data", LEGACY_DATA_DIR, HOST_ROOT),
    )
    copy_legacy_runtime_file(
        "ls_elza_knowledge.md",
        DATA_DIR,
        (LEGACY_PACKAGE_DIR / "Data", LEGACY_DATA_DIR, HOST_ROOT),
    )
    copy_legacy_runtime_file(
        "Help_LocalSunoDb.md",
        DATA_DIR,
        (LEGACY_PACKAGE_DIR / "Data", LEGACY_DATA_DIR, HOST_ROOT),
    )
    copy_legacy_runtime_file(
        "ls_elza_router_diagnostics.jsonl",
        LOGS_DIR,
        (LEGACY_PACKAGE_DIR / "Logs", LEGACY_LOGS_DIR, HOST_ROOT),
    )

HISTORY_PATH = DATA_DIR / "ls_elza_history.json"
KNOWLEDGE_PATH = DATA_DIR / "ls_elza_knowledge.md"
HELP_PATH = DATA_DIR / "Help_LocalSunoDb.md"
BUNDLED_KNOWLEDGE_PATH = Path(__file__).resolve().with_name("ls_elza_knowledge.md")
ROUTER_DIAGNOSTICS_PATH = LOGS_DIR / "ls_elza_router_diagnostics.jsonl"

DEFAULT_MODEL = "gpt-5.6-luna"
MAX_USER_MESSAGE_CHARS = 12000
MAX_CONTEXT_TEXT_CHARS = 2000
MAX_KNOWLEDGE_CHARS = 30000
MAX_SELECTED_TRACK_IDS = 50
MAX_API_HISTORY_MESSAGES = 24
MAX_API_HISTORY_CHARS = 50000
MAX_STORED_MESSAGES_PER_CHAT = 300
MAX_READONLY_TOOL_ROUNDS = 4
MAX_READONLY_TOOL_CALLS = 8
MAX_READONLY_TOOL_OUTPUT_CHARS = 30000
MAX_IMAGES_PER_MESSAGE = 4
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_TOTAL_IMAGE_BYTES = 12 * 1024 * 1024
ALLOWED_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}
ALLOWED_IMAGE_DETAILS = {"low", "high", "original", "auto"}
ALLOWED_ANSWER_SOURCE_IDS = {
    "ls_context",
    "ls_help",
    "image",
    "db",
    "code",
    "local",
}
ALLOWED_ANSWER_SOURCE_KINDS = {"provided", "consulted", "local"}
ALLOWED_SELECTED_MODES = {"", "UX_REVIEW", "TEST_REVIEW", "TRACK_DB", "LS_CODE"}

_HISTORY_LOCK = threading.RLock()
_SEND_LOCK = threading.Lock()
_ROUTER_DIAGNOSTICS_LOCK = threading.Lock()


# 3.  ------ LS Elza instructions -----

LS_ELZA_INSTRUCTIONS = """
You are LS Elza, the local AI assistant inside LocalSunoDb.

Always answer the user in Latvian unless the user explicitly requests another
language. Use the supplied LocalSunoDb context and do not ask for information
that is already present there.

Your role in this version is consultation only. You may explain the interface,
interpret the current context, identify a likely next step, and guide the user.
You cannot and must not claim to have changed a database, edited or moved a
file, started Refresh DB, downloaded audio, changed Local family title, changed
Stem links, or executed PowerShell or Python commands.

You have no write tools and no unrestricted access to the LocalSunoDb database
or file system. You may receive a small set of explicitly named read-only LS
tools. Use those tools for database counts, title searches, exact Track ID
facts, persistent Local family confirmation, and inspection of bounded excerpts
from the currently running LocalSunoDb source. Never imply that a read-only tool
changed anything. Treat supplied context and tool results as factual data. If
information is missing, state exactly what is unavailable instead of inventing
it.

A read-only restriction prohibits changing files or data, not analysis. When
the relevant bounded source is available, use it to determine and explain the
observed cause instead of replying that a read-only check was stopped. You may
offer to prepare a concise Codex-ready repair prompt that describes the verified
cause and requested result. Never edit files, create a release or ZIP, execute
source or commands, or claim that a proposed repair was applied.

The supplied current context describes dynamic UI state, such as the active
tab, current selection, title, category, and Local family title. Missing
dynamic context does not cancel verified general LocalSunoDb knowledge. For a
question about how a LocalSunoDb feature generally works, answer from the
verified knowledge even when no track is selected. Say that information is
unavailable only when neither the current context nor the verified knowledge
contains the answer. Do not replace a known rule with speculation such as
"if this feature exists" or "it might".

The context may include a "view" object. It describes the currently applied
search, Workspace and Type filters, exact matching-result count, loaded-row
count, selected-row count, and WAV selection-mode state. Keep the selected
track's "workspace" separate from "view.workspace_filter". A null Workspace
filter means all workspaces. Do not confuse loaded rows with the exact result
count when only part of a result set is rendered.

For practical LocalSunoDb tasks, default to SPS mode: give one concrete action,
then ask the user to reply Ok or Fail before giving the next action. Do not use
SPS for a simple factual answer that does not require the user to perform a
sequence of actions.

Keep answers concise and practical. Never expose or request the OpenAI API key.

In LocalSunoDb, the user may call the five user Flags “karodziņi”, “Flags”,
“zvaigznītes”, or use the compact tokens 1+* ... 5+*. Numbers 1 through 5
refer to those five LS Flags. When several Flags are requested with “un/and”,
LS Filter Library semantics require all of them (AND). Do not ask what a
numbered karodziņš means when this wording is used.

When the user asks to select, filter, show, find, or list LocalSunoDb tracks,
use the ls_prepare_selection tool before answering. Interpret the request by
semantic meaning rather than exact spelling, and tolerate ordinary typing and
speech-to-text errors. Preserve every stated condition; never silently drop a
category, Flag, tag, Workspace, Local family, local-audio condition, or title
condition because one word is misspelled. If the request is ambiguous or asks
for a combination that cannot be represented safely, call ls_prepare_selection
with safe_to_execute=false and a short reason. Never invent SQL or construct a
filter URL yourself. The host validates the structured request and executes the
existing read-only LS filter logic.

For selection requests, distinguish the visible LS Type badge from the
Song/Instrumental category. When the user says local WAV, set local_audio to
"with" and local_audio_extensions to ["wav"]. When the user says "bez Upload",
"- Upload", "izņem Upload", or an obvious misspelling such as "Uplod", preserve
that condition with exclude_ui_types=["Upload"]. Do not tell the user that a
new UI filter is required merely because this combination is not exposed in
the normal filter controls: ls_prepare_selection can return an exact Track ID
selection and the host will provide the "Atvērt atlasi LS" action.

When the user asks for a word to be found "in a tag or elsewhere", "tagā vai
citur", "jebkur", "anywhere", or equivalent wording, set anywhere_query to that
requested word or phrase. anywhere_query means Name/Track ID OR Lyrics OR
Prompt OR Tags. Do not encode a grammatical phrase such as "#tagā" as a literal
requested tag. Leave tags empty unless the user names an actual tag value such
as #Elizabete.

If the user sends only a brief acknowledgement, thanks, approval, farewell, or
emoji reaction without a new question, reply naturally in one short sentence.
Do not call tools and do not append database counts, search state, selection,
filters, code facts, or other context that the user did not ask about.

Images may be attached only for the current turn. Analyze them together with
the user's text. The image bytes are not retained in local chat history. Do not
claim that a previous image remains available in a later turn; rely on the
earlier textual answer or ask the user to attach the image again when needed.

When UX_REVIEW is active or the user explicitly asks to review the current
screen, act as a UX/help reviewer rather than a code reviewer. Evaluate the UI
in this strict evidence order:

1. Visible UI: describe only controls, labels, layout, hierarchy, spacing,
   states and messages that are actually visible in an image attached to the
   current turn or explicitly listed as visible UI elements in the supplied
   screen context.
2. Supplied state context: separately report relevant dynamic facts such as the
   active tab, filters, result counts, loaded-row count and selection. Do not
   present these data as a visual description of the interface.
3. Findings: identify UX strengths and problems supported by the visible UI or
   supplied state. Prioritize actionable findings as high, medium or low.
4. Missing evidence: state briefly what cannot be assessed without a current
   screenshot or richer visible-elements context.

Never infer that a control, pagination option, tooltip, close button, detail
panel or other visual element is present or absent merely because the state
context does not mention it. Never treat a URL parameter as proof that a notice
or control is visible. Do not criticize terminology unless the actual visible
label is supplied. If no current image or visible-elements description is
available, say that only the screen state can be described and do not claim a
full visual UX review.

Focus first on screen structure, control grouping, action hierarchy, clarity,
discoverability, consistency, feedback and error prevention. Mention database
counts, filters and selection only when they materially affect the user's UX
question. Do not turn a broad UI-description question into a database-status
report.

Use only the supplied read-only screen context and any image attached for the
current turn. Identify unclear controls, missing tooltips, explanations or
warnings, candidates for an Advanced group, and elements that are already
clear. Do not use database tools merely to complete a screen review. Use the
bounded source-inspection tools when the user asks where a control went, why
the interface behaves in a particular way, how an LS function is implemented,
or when code evidence is needed to answer a practical "how to" question.
Determine and explain the observed cause when the source provides it. A UX
review may recommend interface wording or organization and may offer a
Codex-ready repair prompt, but any change to database, API, Downloader or other
application logic must be proposed separately. Never claim that the review
changed LocalSunoDb.

When TEST_REVIEW is active, act as an embedded LocalSunoDb function tester.
Use the current-turn screenshot, the supplied read-only LS state, and the
user's description of the action and expected result. Do not invent an action,
previous screen state, click sequence, expected result, or hidden application
behavior that was not supplied or visibly evidenced.

Return a compact test report in this order:

1. Test: the function or action being checked.
2. Observed result: only what the current evidence proves.
3. Verdict: PASS, FAIL, or UNCLEAR. PASS requires evidence that the stated
   expected result occurred; FAIL requires evidence of a contradiction;
   otherwise use UNCLEAR.
4. Problem: for FAIL, state the exact mismatch without guessing its code cause.
5. Next check: give one concrete SPS action only when another check is needed.

If the user did not state the action or expected result, infer it only when it
is unambiguous from the question and visible UI. Otherwise return UNCLEAR and
ask for the single missing fact. Distinguish visual evidence from supplied
state context. Do not use database or source-code tools in TEST_REVIEW, do not
change LocalSunoDb, and never claim that the test repaired anything.

When explicit TRACK_DB mode is active, analyze exactly one selected track.
Use the supplied selected Track ID and the two Track tools. Return a compact
report in this order: Suno data; local audio; Stems; Local family; data gaps;
recommended next action. Separate verified facts from unavailable details.
Do not infer a WAV extension, file path, Local family membership, or Stem
health when the tools do not provide that evidence.
Recommend only actions whose exact control or workflow is confirmed by the
supplied context or verified LocalSunoDb knowledge. Never tell the user to
inspect a file format or confirm Local family in the Selected Track panel
unless the available evidence explicitly confirms that capability there.
When no confirmed action can resolve a data gap, state which information is
unavailable instead of inventing a panel, button, or workflow.
""".strip()

READONLY_TOOLS_HEADER = """
The local service provides four strictly read-only LocalSunoDb tools. Use them
when the user asks for actual database facts that are not already present in
the current UI context. Prefer a tool result over estimating from general
knowledge. Title similarity is not proof of Local family membership; use the
persistent Local family status tool for that question. Tool results cannot
authorize or perform a write operation.

"Suno Database" names the LS tab; it does not mean the selected track's
Workspace. For a database-wide title search, search all active LS workspaces.
Pass a Workspace filter only when the user explicitly asks for a named
Workspace. Never infer a Workspace restriction from the selected track, Local
family title, current URL, or earlier conversation.
""".strip()

READONLY_TOOLS_UNAVAILABLE_NOTICE = """
The local read-only LocalSunoDb data tools are unavailable for this request.
Do not estimate database counts or claim to have inspected a Track ID.
""".strip()

CODE_TOOLS_HEADER = """
The local service also provides strictly read-only source-inspection tools for
the LocalSunoDb.py file that is currently running. Use them when the user
asks how the actual current LS code behaves and verified knowledge does not
settle the question. Start with ls_code_search using distinctive visible text,
an element ID, endpoint or function name. Then use ls_read_code_lines or
ls_read_function only for the relevant bounded excerpt. Do not request the
whole file. The tools cannot select another path, write code, execute source,
or expose stored API keys. Clearly distinguish an observed implementation from
a general recommendation.
""".strip()

CODE_TOOLS_UNAVAILABLE_NOTICE = """
The read-only LocalSunoDb source-inspection tools are unavailable. Do not claim
to have inspected the currently running app code.
""".strip()

KNOWLEDGE_HEADER = """
Verified LocalSunoDb knowledge follows. Sections marked CURRENT are bundled
with this LS Elza build and have priority for general feature behavior. Migrated
Help and legacy knowledge are supplemental: use them only when they do not
conflict with CURRENT knowledge, current read-only LS context, or verified
current-code inspection. The supplied current context has priority for dynamic
values such as active tab, current selection, titles, settings, and app version.
If the answer is absent or sources conflict, say what is unknown instead of
inventing a LocalSunoDb rule.
""".strip()

KNOWLEDGE_UNAVAILABLE_NOTICE = """
The verified LocalSunoDb knowledge file is not available for this request.
Use only the supplied read-only context and clearly identify missing facts.
""".strip()


# 4.  ------ Errors -----

class LSElzaError(RuntimeError):
    def __init__(self, message, status=500, code="ls_elza_error"):
        super().__init__(message)
        self.status = int(status)
        self.code = str(code or "ls_elza_error")


# 5.  ------ General helpers -----

def now_iso_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean_text(value, max_chars):
    text = str(value or "").strip()
    if len(text) > int(max_chars):
        text = text[: int(max_chars)].rstrip()
    return text


def normalize_answer_sources(value):
    """Keep only compact, display-safe source metadata generated by this service."""
    if not isinstance(value, list):
        return []

    result = []
    seen = set()
    for item in value[:12]:
        if not isinstance(item, dict):
            continue
        source_id = clean_text(item.get("id"), 40).lower()
        if source_id not in ALLOWED_ANSWER_SOURCE_IDS or source_id in seen:
            continue
        label = clean_text(item.get("label"), 80)
        if not label:
            continue
        kind = clean_text(item.get("kind"), 30).lower()
        if kind not in ALLOWED_ANSWER_SOURCE_KINDS:
            kind = "provided"
        seen.add(source_id)
        result.append({
            "id": source_id,
            "label": label,
            "kind": kind,
            "detail": clean_text(item.get("detail"), 700),
        })
    return result


def _image_signature_matches(data, mime_type):
    if mime_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if mime_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if mime_type == "image/webp":
        return (
            len(data) >= 12
            and data.startswith(b"RIFF")
            and data[8:12] == b"WEBP"
        )
    return False


def normalize_ls_images(value):
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise LSElzaError(
            "LS Elza images must be supplied as a list.",
            status=400,
            code="invalid_images",
        )
    if len(value) > MAX_IMAGES_PER_MESSAGE:
        raise LSElzaError(
            f"Attach no more than {MAX_IMAGES_PER_MESSAGE} images at once.",
            status=400,
            code="too_many_images",
        )

    result = []
    total_bytes = 0
    for item in value:
        if not isinstance(item, dict):
            raise LSElzaError(
                "Each LS Elza image must be an object.",
                status=400,
                code="invalid_image",
            )
        mime_type = clean_text(item.get("mime_type"), 80).lower()
        if mime_type not in ALLOWED_IMAGE_MIME_TYPES:
            raise LSElzaError(
                "LS Elza accepts PNG, JPEG and WebP images.",
                status=400,
                code="unsupported_image_type",
            )
        encoded = item.get("data_base64")
        if not isinstance(encoded, str) or not encoded:
            raise LSElzaError(
                "An attached image has no readable data.",
                status=400,
                code="missing_image_data",
            )
        max_encoded_chars = ((MAX_IMAGE_BYTES + 2) // 3) * 4 + 16
        if len(encoded) > max_encoded_chars:
            raise LSElzaError(
                "An attached image exceeds the 5 MB limit.",
                status=400,
                code="image_too_large",
            )
        try:
            data = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as error:
            raise LSElzaError(
                "An attached image is not valid Base64 data.",
                status=400,
                code="invalid_image_data",
            ) from error
        if not data or len(data) > MAX_IMAGE_BYTES:
            raise LSElzaError(
                "An attached image exceeds the 5 MB limit.",
                status=400,
                code="image_too_large",
            )
        if not _image_signature_matches(data, mime_type):
            raise LSElzaError(
                "An attached image does not match its declared file type.",
                status=400,
                code="image_signature_mismatch",
            )
        total_bytes += len(data)
        if total_bytes > MAX_TOTAL_IMAGE_BYTES:
            raise LSElzaError(
                "The attached images exceed the 12 MB total limit.",
                status=400,
                code="images_too_large",
            )
        detail = clean_text(item.get("detail"), 20).lower() or "high"
        if detail not in ALLOWED_IMAGE_DETAILS:
            detail = "high"
        result.append({
            "name": clean_text(item.get("name"), 240) or "image",
            "mime_type": mime_type,
            "data_base64": encoded,
            "byte_size": len(data),
            "detail": detail,
        })
    return result


_ACKNOWLEDGEMENT_WORDS = {
    "ok", "okay", "labi", "skaidrs", "saprotu", "sapratu", "jā", "ja",
    "paldies", "super", "supper", "lieliski", "ideāli", "forši", "bravo",
    "atā", "ata", "čau", "chau", "thanks", "thank", "you",
}
_ACKNOWLEDGEMENT_EMOJIS = set("👍👌😊🙂😀😄😁❤️❤🙏👏✅🎉💯")


def is_simple_acknowledgement(value):
    text = clean_text(value, 160)
    if not text:
        return False
    words = [
        item.casefold()
        for item in re.findall(r"[^\W\d_]+", text, flags=re.UNICODE)
    ]
    if words and all(item in _ACKNOWLEDGEMENT_WORDS for item in words):
        return True
    alphanumeric = re.sub(r"[^\w]+", "", text, flags=re.UNICODE)
    return (
        not alphanumeric
        and len(text) <= 24
        and any(character in _ACKNOWLEDGEMENT_EMOJIS for character in text)
    )


def acknowledgement_answer(value):
    folded = clean_text(value, 160).casefold()
    if "paldies" in folded or "thank" in folded:
        return "Lūdzu! 😊"
    if "atā" in folded or "ata" in folded or "čau" in folded or "chau" in folded:
        return "Uz redzēšanos! 😊"
    return "Labi! 😊"


def _read_knowledge_file(path):
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def load_ls_elza_knowledge():
    """Load current bundled knowledge plus optional migrated Help supplements."""
    sections = []

    bundled = _read_knowledge_file(BUNDLED_KNOWLEDGE_PATH)
    if bundled:
        sections.append("[CURRENT VERIFIED KNOWLEDGE]\n" + bundled)

    help_text = _read_knowledge_file(HELP_PATH)
    if help_text:
        sections.append(
            "[MIGRATED HELP — SUPPLEMENTAL, MAY PREDATE CURRENT BUILD]\n"
            + help_text
        )

    legacy_knowledge = _read_knowledge_file(KNOWLEDGE_PATH)
    if legacy_knowledge:
        sections.append(
            "[LEGACY KNOWLEDGE — SUPPLEMENTAL, MAY PREDATE CURRENT BUILD]\n"
            + legacy_knowledge
        )

    if not sections:
        return ""
    return clean_text("\n\n".join(sections), MAX_KNOWLEDGE_CHARS)


def database_tools_available():
    return callable(get_readonly_tool_definitions) and callable(run_readonly_action)


def code_tools_available():
    return (
        callable(configure_code_reader_source)
        and callable(get_code_tool_definitions)
        and callable(run_code_action)
    )


def readonly_tools_available():
    return database_tools_available() or code_tools_available()


def configure_ls_elza_app_source(path):
    if not code_tools_available():
        raise LSElzaError(
            "The LS Elza read-only code reader could not be loaded.",
            status=503,
            code="code_reader_unavailable",
        )
    try:
        return configure_code_reader_source(path)
    except Exception as error:
        raise LSElzaError(
            "The running LocalSunoDb source could not be bound to LS Elza.",
            status=503,
            code="code_reader_configuration_failed",
        ) from error


def get_available_readonly_tools():
    tools = []
    if database_tools_available():
        try:
            database_tools = get_readonly_tool_definitions()
        except Exception:
            database_tools = []
        if isinstance(database_tools, list):
            tools.extend(database_tools)
    if code_tools_available():
        try:
            code_tools = get_code_tool_definitions()
        except Exception:
            code_tools = []
        if isinstance(code_tools, list):
            tools.extend(code_tools)

    tools.append(get_selection_tool_definition())

    # Workspace routing fix: 13.jul.2026   12:23
    # Reinforce the global default directly in the tool schema seen by the model.
    for tool in tools:
        if not isinstance(tool, dict) or tool.get("name") != "ls_search_titles":
            continue
        tool["description"] = (
            str(tool.get("description") or "").rstrip()
            + " Search all active LS workspaces unless the user explicitly "
            "requests one named Workspace."
        )
        parameters = tool.get("parameters")
        properties = parameters.get("properties") if isinstance(parameters, dict) else None
        workspace = properties.get("workspace") if isinstance(properties, dict) else None
        if isinstance(workspace, dict):
            workspace["description"] = (
                "Optional exact Workspace name. Set this only when the user "
                "explicitly requests that Workspace; otherwise omit it."
            )
    validate_openai_tool_definitions(tools)
    return tools


def get_track_readonly_tools():
    allowed_names = {"ls_track_summary", "ls_local_family_status"}
    return [
        tool for tool in get_available_readonly_tools()
        if isinstance(tool, dict) and tool.get("name") in allowed_names
    ]


def get_code_readonly_tools():
    allowed_names = {
        "ls_code_search",
        "ls_read_code_lines",
        "ls_read_function",
        "ls_app_structure",
    }
    return [
        tool for tool in get_available_readonly_tools()
        if isinstance(tool, dict) and tool.get("name") in allowed_names
    ]


def build_ls_elza_instructions():
    knowledge = load_ls_elza_knowledge()
    data_tool_notice = (
        READONLY_TOOLS_HEADER
        if database_tools_available()
        else READONLY_TOOLS_UNAVAILABLE_NOTICE
    )
    code_tool_notice = (
        CODE_TOOLS_HEADER
        if code_tools_available()
        else CODE_TOOLS_UNAVAILABLE_NOTICE
    )
    tool_notice = data_tool_notice + "\n\n" + code_tool_notice
    if not knowledge:
        return (
            LS_ELZA_INSTRUCTIONS
            + "\n\n"
            + tool_notice
            + "\n\n"
            + KNOWLEDGE_UNAVAILABLE_NOTICE
        )

    return (
        LS_ELZA_INSTRUCTIONS
        + "\n\n"
        + tool_notice
        + "\n\n"
        + KNOWLEDGE_HEADER
        + "\n\n<ls_elza_knowledge>\n"
        + knowledge
        + "\n</ls_elza_knowledge>"
    )


def new_chat_id():
    return uuid.uuid4().hex


def empty_history():
    return {
        "schema_version": 2,
        "active_chat_id": "",
        "chats": {},
    }


def new_chat_record(chat_id=None):
    timestamp = now_iso_utc()
    return {
        "id": clean_text(chat_id, 80) or new_chat_id(),
        "created_at": timestamp,
        "updated_at": timestamp,
        "messages": [],
    }


def public_message(message):
    result = {
        "role": clean_text(message.get("role"), 20),
        "content": clean_text(message.get("content"), MAX_USER_MESSAGE_CHARS * 2),
        "created_at": clean_text(message.get("created_at"), 80),
    }
    sources = normalize_answer_sources(message.get("sources"))
    if sources:
        result["sources"] = sources
    return result


def public_chat_payload(chat):
    return {
        "chat_id": chat.get("id", ""),
        "created_at": chat.get("created_at", ""),
        "updated_at": chat.get("updated_at", ""),
        "messages": [public_message(item) for item in chat.get("messages", [])],
    }


# 6.  ------ Local history -----

def normalize_history(data):
    if not isinstance(data, dict):
        return empty_history()

    chats = data.get("chats")
    if not isinstance(chats, dict):
        chats = {}

    normalized_chats = {}
    for raw_chat_id, raw_chat in chats.items():
        chat_id = clean_text(raw_chat_id, 80)
        if not chat_id or not isinstance(raw_chat, dict):
            continue

        chat = new_chat_record(chat_id)
        chat["created_at"] = clean_text(raw_chat.get("created_at"), 80) or chat["created_at"]
        chat["updated_at"] = clean_text(raw_chat.get("updated_at"), 80) or chat["updated_at"]

        raw_messages = raw_chat.get("messages")
        if isinstance(raw_messages, list):
            for item in raw_messages[-MAX_STORED_MESSAGES_PER_CHAT:]:
                if not isinstance(item, dict):
                    continue
                role = clean_text(item.get("role"), 20)
                content = clean_text(item.get("content"), MAX_USER_MESSAGE_CHARS * 2)
                if role not in {"user", "assistant"} or not content:
                    continue
                chat["messages"].append({
                    "role": role,
                    "content": content,
                    "created_at": clean_text(item.get("created_at"), 80) or now_iso_utc(),
                    "sources": (
                        normalize_answer_sources(item.get("sources"))
                        if role == "assistant"
                        else []
                    ),
                })

        normalized_chats[chat_id] = chat

    active_chat_id = clean_text(data.get("active_chat_id"), 80)
    if active_chat_id not in normalized_chats:
        active_chat_id = ""

    return {
        "schema_version": 2,
        "active_chat_id": active_chat_id,
        "chats": normalized_chats,
    }


def load_history_unlocked():
    if not HISTORY_PATH.exists():
        return empty_history()

    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LSElzaError(
            "LS Elza chat history could not be read.",
            status=500,
            code="history_read_failed",
        ) from error

    return normalize_history(data)


def save_history_unlocked(history):
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = HISTORY_PATH.with_name(HISTORY_PATH.name + ".tmp")
    content = json.dumps(history, ensure_ascii=False, indent=2)

    try:
        temporary_path.write_text(content, encoding="utf-8")
        os.replace(temporary_path, HISTORY_PATH)
    except OSError as error:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise LSElzaError(
            "LS Elza chat history could not be saved.",
            status=500,
            code="history_write_failed",
        ) from error


def get_or_create_chat_unlocked(history, requested_chat_id=""):
    chat_id = clean_text(requested_chat_id, 80)
    if not chat_id:
        chat_id = clean_text(history.get("active_chat_id"), 80)

    chats = history.setdefault("chats", {})
    chat = chats.get(chat_id) if chat_id else None

    if not isinstance(chat, dict):
        chat = new_chat_record()
        chat_id = chat["id"]
        chats[chat_id] = chat

    history["active_chat_id"] = chat_id
    return chat


def load_chat(chat_id=""):
    with _HISTORY_LOCK:
        history = load_history_unlocked()
        chat = get_or_create_chat_unlocked(history, chat_id)
        save_history_unlocked(history)
        return public_chat_payload(chat)


def create_new_chat():
    with _HISTORY_LOCK:
        history = load_history_unlocked()
        chat = new_chat_record()
        history.setdefault("chats", {})[chat["id"]] = chat
        history["active_chat_id"] = chat["id"]
        save_history_unlocked(history)
        return public_chat_payload(chat)


def clear_chat(chat_id=""):
    with _HISTORY_LOCK:
        history = load_history_unlocked()
        chat = get_or_create_chat_unlocked(history, chat_id)
        chat["messages"] = []
        chat["updated_at"] = now_iso_utc()
        save_history_unlocked(history)
        return public_chat_payload(chat)


def append_chat_exchange(
    chat_id,
    user_text,
    assistant_text,
    assistant_sources=None,
):
    timestamp = now_iso_utc()

    with _HISTORY_LOCK:
        history = load_history_unlocked()
        chat = get_or_create_chat_unlocked(history, chat_id)
        chat["messages"].extend([
            {
                "role": "user",
                "content": user_text,
                "created_at": timestamp,
            },
            {
                "role": "assistant",
                "content": assistant_text,
                "created_at": now_iso_utc(),
                "sources": normalize_answer_sources(assistant_sources),
            },
        ])
        chat["messages"] = chat["messages"][-MAX_STORED_MESSAGES_PER_CHAT:]
        chat["updated_at"] = now_iso_utc()
        save_history_unlocked(history)
        return public_chat_payload(chat)


# 7.  ------ LocalSunoDb context -----

def normalize_selected_track_ids(value):
    if not isinstance(value, list):
        value = []

    result = []
    seen = set()
    for item in value:
        track_id = clean_text(item, 120)
        key = track_id.lower()
        if not track_id or key in seen:
            continue
        seen.add(key)
        result.append(track_id)
        if len(result) >= MAX_SELECTED_TRACK_IDS:
            break
    return result


def normalize_context_string_list(value, max_items=20, max_chars=120):
    if not isinstance(value, list):
        return []

    result = []
    seen = set()
    for item in value:
        text = clean_text(item, max_chars)
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        result.append(text)
        if len(result) >= int(max_items):
            break
    return result


def normalize_context_count(value):
    if value is None or value == "":
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, number)


def normalize_context_filters(value):
    source = value if isinstance(value, dict) else {}
    result = {}
    for key, item in list(source.items())[:30]:
        clean_key = clean_text(key, 80)
        if not clean_key:
            continue
        if item is None or isinstance(item, (bool, int, float)):
            result[clean_key] = item
        else:
            result[clean_key] = clean_text(item, 500) or None
    return result


def normalize_ui_controls(value, max_items=40):
    if not isinstance(value, list):
        return []
    result = []
    for item in value[:max_items]:
        if not isinstance(item, dict):
            continue
        label = clean_text(item.get("label"), 120)
        if not label:
            continue
        normalized = {"label": label, "enabled": bool(item.get("enabled", True))}
        if "checked" in item:
            normalized["checked"] = bool(item.get("checked"))
        if "value" in item:
            normalized["value"] = clean_text(item.get("value"), 120) or None
        result.append(normalized)
    return result


def normalize_view_context(value):
    source = value if isinstance(value, dict) else {}
    return {
        "view_name": clean_text(source.get("view_name"), 80) or None,
        "search_text": clean_text(
            source.get("search_text"),
            MAX_CONTEXT_TEXT_CHARS,
        ) or None,
        "search_draft_text": clean_text(
            source.get("search_draft_text"),
            MAX_CONTEXT_TEXT_CHARS,
        ) or None,
        "style_search_text": clean_text(
            source.get("style_search_text"),
            MAX_CONTEXT_TEXT_CHARS,
        ) or None,
        "search_fields": normalize_context_string_list(
            source.get("search_fields"),
        ),
        "workspace_filter": clean_text(
            source.get("workspace_filter"),
            MAX_CONTEXT_TEXT_CHARS,
        ) or None,
        "type_filter": clean_text(source.get("type_filter"), 120) or None,
        "type_filter_label": clean_text(
            source.get("type_filter_label"),
            200,
        ) or None,
        "result_count": normalize_context_count(source.get("result_count")),
        "loaded_row_count": normalize_context_count(
            source.get("loaded_row_count")
        ),
        "selected_row_count": normalize_context_count(
            source.get("selected_row_count")
        ),
        "row_limit": clean_text(source.get("row_limit"), 80) or None,
        "wav_selection_mode": bool(source.get("wav_selection_mode")),
        "filters": normalize_context_filters(source.get("filters")),
        "visible_buttons": normalize_ui_controls(source.get("visible_buttons"), 40),
        "visible_checkboxes": normalize_ui_controls(source.get("visible_checkboxes"), 30),
        "visible_selects": normalize_ui_controls(source.get("visible_selects"), 20),
        "last_ui_action": clean_text(source.get("last_ui_action"), 160) or None,
    }


def normalize_ls_context(value):
    source = value if isinstance(value, dict) else {}
    selected_track_ids = normalize_selected_track_ids(source.get("selected_track_ids"))
    selected_track_id = clean_text(source.get("selected_track_id"), 120)

    if len(selected_track_ids) == 1:
        selected_track_id = selected_track_ids[0]
    elif len(selected_track_ids) != 1:
        selected_track_id = ""

    return {
        "active_tab": clean_text(source.get("active_tab"), 80),
        "current_url": clean_text(source.get("current_url"), MAX_CONTEXT_TEXT_CHARS),
        "selected_track_id": selected_track_id or None,
        "selected_track_ids": selected_track_ids,
        "selected_count": len(selected_track_ids),
        "title": clean_text(source.get("title"), MAX_CONTEXT_TEXT_CHARS) or None,
        "workspace": clean_text(source.get("workspace"), MAX_CONTEXT_TEXT_CHARS) or None,
        "main_category": clean_text(source.get("main_category"), 80) or None,
        "main_category_source": clean_text(
            source.get("main_category_source"),
            80,
        ) or None,
        "track_kind": clean_text(source.get("track_kind"), 80) or None,
        "local_family_title": clean_text(
            source.get("local_family_title"),
            MAX_CONTEXT_TEXT_CHARS,
        ) or None,
        "app_version": clean_text(source.get("app_version"), 80),
        "view": normalize_view_context(source.get("view")),
    }


def format_context_for_model(context):
    # Build the immutable Core snapshot on every request while preserving the
    # existing model-facing JSON contract during this compatibility migration.
    build_core_context_snapshot(context)
    return json.dumps(context, ensure_ascii=False, indent=2)


# 8.  ------ OpenAI request -----

def get_openai_client():
    if OpenAI is None:
        raise LSElzaError(
            "The OpenAI Python package is not installed.",
            status=503,
            code="openai_package_missing",
        )

    api_key = clean_text(os.environ.get("OPENAI_API_KEY"), 1000)
    if not api_key:
        raise LSElzaError(
            "OPENAI_API_KEY is not configured for this Windows user.",
            status=503,
            code="openai_key_missing",
        )

    return OpenAI(api_key=api_key, timeout=60.0, max_retries=1)


def get_model_name():
    return clean_text(os.environ.get("LS_ELZA_MODEL"), 120) or DEFAULT_MODEL


def build_api_history(messages):
    if not isinstance(messages, list):
        return []

    result = []
    used_chars = 0
    for item in reversed(messages[-MAX_API_HISTORY_MESSAGES:]):
        if not isinstance(item, dict):
            continue
        role = clean_text(item.get("role"), 20)
        content = clean_text(item.get("content"), MAX_USER_MESSAGE_CHARS * 2)
        if role not in {"user", "assistant"} or not content:
            continue
        if used_chars + len(content) > MAX_API_HISTORY_CHARS:
            break
        result.append({"role": role, "content": content})
        used_chars += len(content)

    result.reverse()
    return result


# 8A. ------ Read-only tool orchestration -----
# Added: 13.jul.2026   12:14

def _response_item_value(item, name, default=None):
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _response_item_for_input(item):
    if isinstance(item, dict):
        return dict(item)
    model_dump = getattr(item, "model_dump", None)
    if callable(model_dump):
        return model_dump(exclude_none=True)
    raise LSElzaError(
        "The OpenAI API returned an unsupported tool response item.",
        status=502,
        code="openai_tool_item_invalid",
    )


def _function_calls_from_response(response):
    output = getattr(response, "output", None)
    if not isinstance(output, list):
        return []
    return [
        item
        for item in output
        if _response_item_value(item, "type") == "function_call"
    ]


CODE_READER_ACTIONS = {
    "ls_code_search",
    "ls_read_function",
    "ls_read_code_lines",
    "ls_app_structure",
}

DB_ACTION_LABELS = {
    "ls_database_summary": "DB summary",
    "ls_search_titles": "Title search",
    "ls_track_summary": "Track summary",
    "ls_local_family_status": "Local family status",
}


def _source_trace_record(action, data):
    if action == SELECTION_TOOL_NAME:
        source_id = "selection"
    elif action in CODE_READER_ACTIONS:
        source_id = "code"
    elif action in DB_ACTION_LABELS:
        source_id = "db"
    else:
        return None
    return {
        "source_id": source_id,
        "action": action,
        "data": data if isinstance(data, dict) else {},
    }


def _bounded_code_ranges(data):
    ranges = []

    def add_range(start, end):
        try:
            start_number = max(1, int(start))
            end_number = max(start_number, int(end))
        except (TypeError, ValueError):
            return
        ranges.append((start_number, end_number))

    if isinstance(data, dict):
        add_range(data.get("start_line"), data.get("end_line"))
        for snippet in data.get("snippets", [])[:12]:
            if isinstance(snippet, dict):
                add_range(snippet.get("start_line"), snippet.get("end_line"))
        for item in data.get("items", [])[:12]:
            if isinstance(item, dict):
                add_range(item.get("line"), item.get("end_line", item.get("line")))

    merged = []
    for start, end in sorted(set(ranges)):
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged[:8]


def _tool_answer_sources(trace):
    trace = trace if isinstance(trace, list) else []
    sources = []

    db_actions = []
    for item in trace:
        if not isinstance(item, dict) or item.get("source_id") != "db":
            continue
        action = clean_text(item.get("action"), 100)
        if action and action not in db_actions:
            db_actions.append(action)
    if db_actions:
        sources.append({
            "id": "db",
            "label": "DB read-only",
            "kind": "consulted",
            "detail": "Sekmīgi izsaukti tikai lasīšanas DB rīki: " + ", ".join(
                DB_ACTION_LABELS.get(action, action) for action in db_actions
            ) + ".",
        })

    code_items = [
        item
        for item in trace
        if isinstance(item, dict) and item.get("source_id") == "code"
    ]
    if code_items:
        file_names = []
        actions = []
        ranges = []
        for item in code_items:
            action = clean_text(item.get("action"), 100)
            if action and action not in actions:
                actions.append(action)
            data = item.get("data") if isinstance(item.get("data"), dict) else {}
            candidate_names = [clean_text(data.get("file_name"), 180)]
            for snippet in data.get("snippets", [])[:12]:
                if isinstance(snippet, dict):
                    candidate_names.append(clean_text(snippet.get("file_name"), 180))
            for structure_item in data.get("items", [])[:12]:
                if isinstance(structure_item, dict):
                    candidate_names.append(clean_text(structure_item.get("file_name"), 180))
            for file_name in candidate_names:
                if file_name and file_name not in file_names:
                    file_names.append(file_name)
            ranges.extend(_bounded_code_ranges(data))

        merged_ranges = []
        for start, end in sorted(set(ranges)):
            if merged_ranges and start <= merged_ranges[-1][1] + 1:
                merged_ranges[-1] = (
                    merged_ranges[-1][0],
                    max(merged_ranges[-1][1], end),
                )
            else:
                merged_ranges.append((start, end))
        merged_ranges = merged_ranges[:8]

        version_label = "Code"
        for file_name in file_names:
            match = re.search(r"suno_app_(v\d+_\d+)\.py$", file_name, re.IGNORECASE)
            if match:
                version_label = "Code " + match.group(1).replace("_", ".")
                break

        detail_parts = []
        if file_names:
            detail_parts.append(", ".join(file_names))
        if merged_ranges:
            detail_parts.append(
                "rindas "
                + ", ".join(
                    str(start) if start == end else f"{start}–{end}"
                    for start, end in merged_ranges
                )
            )
        if actions:
            detail_parts.append("rīki: " + ", ".join(actions))
        sources.append({
            "id": "code",
            "label": version_label,
            "kind": "consulted",
            "detail": "Sekmīgi nolasīts pašlaik palaistais LS kods: "
            + " · ".join(detail_parts)
            + ".",
        })

    return sources


def _run_whitelisted_readonly_action(action, arguments):
    if action == SELECTION_TOOL_NAME:
        return normalize_selection_request(arguments)
    if action in CODE_READER_ACTIONS:
        if not code_tools_available():
            raise LSElzaError(
                "The LS Elza code reader is unavailable.",
                status=503,
                code="code_reader_unavailable",
            )
        return run_code_action(action, arguments)
    if not database_tools_available():
        raise LSElzaError(
            "The LS Elza database reader is unavailable.",
            status=503,
            code="database_reader_unavailable",
        )
    return run_readonly_action(action, arguments)


def _readonly_tool_output(tool_call, source_trace=None):
    action = clean_text(_response_item_value(tool_call, "name"), 100)
    call_id = clean_text(_response_item_value(tool_call, "call_id"), 200)
    raw_arguments = _response_item_value(tool_call, "arguments", "{}")

    if not call_id:
        raise LSElzaError(
            "The OpenAI API returned a function call without a call ID.",
            status=502,
            code="openai_tool_call_id_missing",
        )

    try:
        arguments = json.loads(str(raw_arguments or "{}"))
        if not isinstance(arguments, dict):
            raise ValueError("Function arguments must be an object")
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = {
            "ok": False,
            "read_only": True,
            "action": action,
            "error_code": "invalid_tool_arguments",
            "error": "The read-only tool arguments were not valid JSON.",
        }
    else:
        try:
            data = _run_whitelisted_readonly_action(action, arguments)
            payload = {
                "ok": True,
                "read_only": True,
                "action": action,
                "data": data,
            }
            trace_record = _source_trace_record(action, data)
            if trace_record and isinstance(source_trace, list):
                source_trace.append(trace_record)
        except Exception as error:
            is_data_error = (
                LSElzaReadOnlyError is not None
                and isinstance(error, LSElzaReadOnlyError)
            )
            is_code_error = (
                LSElzaCodeReadOnlyError is not None
                and isinstance(error, LSElzaCodeReadOnlyError)
            )
            if is_data_error or is_code_error:
                error_code = clean_text(getattr(error, "code", "readonly_error"), 100)
                error_message = clean_text(str(error), 1000)
            elif isinstance(error, LSElzaError):
                error_code = clean_text(getattr(error, "code", "readonly_error"), 100)
                error_message = clean_text(str(error), 1000)
            else:
                error_code = "readonly_tool_failed"
                error_message = "The local read-only LS query failed."
            payload = {
                "ok": False,
                "read_only": True,
                "action": action,
                "error_code": error_code,
                "error": error_message,
            }

    output_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(output_text) > MAX_READONLY_TOOL_OUTPUT_CHARS:
        payload = {
            "ok": False,
            "read_only": True,
            "action": action,
            "error_code": "readonly_tool_output_too_large",
            "error": "The read-only result was too large; narrow the query.",
        }
        output_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return {
        "type": "function_call_output",
        "call_id": call_id,
        "output": output_text,
    }


def _core_readonly_tool_result(tool_call, source_trace=None):
    """Execute one Core read-only tool call through the existing LS host boundary."""
    action = clean_text(getattr(tool_call, "tool_id", ""), 100)
    call_id = clean_text(getattr(tool_call, "id", ""), 200)
    arguments = getattr(tool_call, "arguments", {})

    if not call_id:
        raise LSElzaError(
            "Elza Core returned a tool call without a call ID.",
            status=502,
            code="openai_tool_call_id_missing",
        )

    if (
        not isinstance(arguments, dict)
        or INVALID_TOOL_ARGUMENTS_KEY in arguments
    ):
        payload = {
            "ok": False,
            "read_only": True,
            "action": action,
            "error_code": "invalid_tool_arguments",
            "error": "The read-only tool arguments were not valid JSON.",
        }
    else:
        try:
            data = _run_whitelisted_readonly_action(action, arguments)
            payload = {
                "ok": True,
                "read_only": True,
                "action": action,
                "data": data,
            }
            trace_record = _source_trace_record(action, data)
            if trace_record and isinstance(source_trace, list):
                source_trace.append(trace_record)
        except Exception as error:
            is_data_error = (
                LSElzaReadOnlyError is not None
                and isinstance(error, LSElzaReadOnlyError)
            )
            is_code_error = (
                LSElzaCodeReadOnlyError is not None
                and isinstance(error, LSElzaCodeReadOnlyError)
            )
            if is_data_error or is_code_error:
                error_code = clean_text(getattr(error, "code", "readonly_error"), 100)
                error_message = clean_text(str(error), 1000)
            elif isinstance(error, LSElzaError):
                error_code = clean_text(getattr(error, "code", "readonly_error"), 100)
                error_message = clean_text(str(error), 1000)
            else:
                error_code = "readonly_tool_failed"
                error_message = "The local read-only LS query failed."
            payload = {
                "ok": False,
                "read_only": True,
                "action": action,
                "error_code": error_code,
                "error": error_message,
            }

    output_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(output_text) > MAX_READONLY_TOOL_OUTPUT_CHARS:
        payload = {
            "ok": False,
            "read_only": True,
            "action": action,
            "error_code": "readonly_tool_output_too_large",
            "error": "The read-only result was too large; narrow the query.",
        }
        output_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    return ToolResult(call_id=call_id, output=output_text)


def _create_openai_response(client, model_input, instructions, tools):
    request = {
        "model": get_model_name(),
        "instructions": instructions,
        "input": model_input,
        "store": False,
        "include": ["reasoning.encrypted_content"],
        "max_output_tokens": 1800,
    }
    if tools:
        request["tools"] = tools
        request["tool_choice"] = "auto"
    return client.responses.create(**request)


def _latest_user_question(model_input):
    """Extract only the current question from the last user input item."""
    for item in reversed(model_input):
        if not isinstance(item, dict) or item.get("role") != "user":
            continue
        content = item.get("content", "")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "input_text":
                    text_parts.append(str(part.get("text", "")))
            text = "\n".join(text_parts)
        else:
            text = str(content or "")
        marker = "User question:\n"
        if marker in text:
            text = text.rsplit(marker, 1)[-1]
        return clean_text(text, MAX_USER_MESSAGE_CHARS)
    return ""


def classify_question_route(user_text):
    """Return a diagnostic route; this does not restrict tools yet."""
    text = clean_text(user_text, MAX_USER_MESSAGE_CHARS).casefold()
    scores = {
        "TEST_REVIEW": 0,
        "UX_REVIEW": 0,
        "UI_HELP": 0,
        "TRACK_DB": 0,
        "LS_CODE": 0,
        "GENERAL": 0,
    }
    reasons = []

    track_terms = (
        "track id", "track_id", "workspace", "local family", "selected track",
        "datubāz", "cik dziesm", "cik ierakst", "stem skait", "has stems",
    )
    code_terms = (
        "kāpēc", "why", "kļūm", "bug", "nedarbojas", "nestrādā",
        "atkal atver", "arvien no jauna", "atkārtoti", "iestrēg",
        "ko dara kods", "kā realizēts", "funkcij", "endpoint",
    )
    ui_terms = (
        "poga", "panel", "ciln", "filtr", "saved view", "shortcut",
        "īsceļ", "kur ", "kā lietot", "ko nozīmē", "refresh", "update",
        "reset", "clear", "downloader", "compare", "select wav",
    )
    general_terms = (
        "suno.com", "suno ai", "suno studio", "suno credits", "suno kredīt",
        "openai", "audacity", "windows", "mūzik", "dziesmas stils",
    )
    ux_review_terms = (
        "review this screen", "review current screen", "ux review",
        "review the screen", "recenzē šo ekrānu", "izvērtē šo ekrānu",
        "novērtē šo ekrānu", "pārskati šo ekrānu",
        "ui draudzīg", "lietotājam draudzīg",
    )

    selected_track_terms = (
        "izvēlētajai dziesmai", "izvēlētās dziesmas", "izvēlētā dziesma",
        "izvēlētajam ierakstam", "izvēlētā ieraksta", "izvēlētais ieraksts",
        "šai dziesmai", "šim ierakstam", "current track", "selected song",
    )
    track_fact_terms = (
        "lokālais audio", "lokālā audio", "local audio", "suno audio",
        "track id", "track_id", "workspace", "local family", "stem",
    )
    ui_location_terms = (
        "kur atrodas", "kur ir", "nav redzama", "nav redzams",
        "kad parādās", "kā atrast", "where is", "not visible",
    )
    has_ui_subject = any(term in text for term in ui_terms)
    is_ui_location_question = (
        has_ui_subject and any(term in text for term in ui_location_terms)
    )
    is_selected_track_fact = (
        any(term in text for term in selected_track_terms)
        and any(term in text for term in track_fact_terms)
    )
    is_ux_review_request = any(term in text for term in ux_review_terms)

    if is_ux_review_request:
        scores["UX_REVIEW"] += 10
        reasons.append("explicit_ux_review")
    if re.search(r"\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b", text):
        scores["TRACK_DB"] += 5
        reasons.append("track_id")
    if is_selected_track_fact:
        scores["TRACK_DB"] += 5
        reasons.append("selected_track_fact")
    for term in track_terms:
        if term in text:
            scores["TRACK_DB"] += 2
            reasons.append("track_db_term")
            break
    for term in code_terms:
        if term in text:
            scores["LS_CODE"] += 2
            reasons.append("behavior_or_code_term")
            break
    for term in ui_terms:
        if term in text:
            scores["UI_HELP"] += 2
            reasons.append("ui_help_term")
            break
    for term in general_terms:
        if term in text:
            scores["GENERAL"] += 2
            reasons.append("general_term")
            break

    if is_ui_location_question:
        scores["UI_HELP"] += 4
        reasons.append("ui_location_or_visibility")
    if scores["LS_CODE"] and scores["UI_HELP"] and not is_ui_location_question:
        scores["LS_CODE"] += 2
        reasons.append("ui_behavior_question")
    if not any(scores.values()):
        scores["UI_HELP"] = 1
        reasons.append("default_ls_help")

    priority = ("TEST_REVIEW", "UX_REVIEW", "TRACK_DB", "LS_CODE", "UI_HELP", "GENERAL")
    route = max(priority, key=lambda name: (scores[name], -priority.index(name)))
    return route, scores, reasons


def _general_ui_help_instruction(route, reasons, selected_mode):
    """Keep general Help answers focused unless current UI state was requested."""
    if selected_mode or route != "UI_HELP":
        return ""
    if "ui_location_or_visibility" in set(reasons or []):
        return ""
    return (
        "\n\nThis is a general LocalSunoDb Help question, not a request to inspect "
        "the current screen. Answer the feature question directly from verified "
        "knowledge. Do not add a 'Visible UI' / 'Redzamais UI' section, do not "
        "say that the current context does not confirm whether the control is "
        "visible, and do not append unrelated current search counts, loaded-row "
        "counts, selection state, or mode state. Mention current UI state only "
        "when the user explicitly asks where a control is, whether it is visible, "
        "what state it is in, or what is happening on the current screen."
    )


def _write_router_diagnostic(route, scores, reasons, user_text, tool_names,
                             tool_rounds, tool_calls_used, outcome,
                             selected_mode=""):
    """Write bounded JSONL diagnostics; logging failures never block Elza."""
    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "route": route,
        "selected_mode": clean_text(selected_mode, 40) or None,
        "scores": scores,
        "reasons": reasons,
        "question": clean_text(user_text, 500),
        "tools": list(tool_names),
        "tool_rounds": int(tool_rounds),
        "tool_calls": int(tool_calls_used),
        "outcome": clean_text(outcome, 100),
    }
    try:
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        with _ROUTER_DIAGNOSTICS_LOCK:
            with ROUTER_DIAGNOSTICS_PATH.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
    except Exception:
        pass


def create_answer_response(
    client,
    model_input,
    selected_mode="",
    *,
    conversation_id="",
    context=None,
):
    """Route LS answer execution through the public Elza Core Contract-v1 facade."""
    user_question = _latest_user_question(model_input)
    route, route_scores, route_reasons = classify_question_route(user_question)
    selected_mode = clean_text(selected_mode, 40).upper()
    if selected_mode in ALLOWED_SELECTED_MODES - {""}:
        route = selected_mode
        route_scores = {
            "TEST_REVIEW": 100 if selected_mode == "TEST_REVIEW" else 0,
            "UX_REVIEW": 100 if selected_mode == "UX_REVIEW" else 0,
            "UI_HELP": 0,
            "TRACK_DB": 100 if selected_mode == "TRACK_DB" else 0,
            "LS_CODE": 100 if selected_mode == "LS_CODE" else 0,
            "GENERAL": 0,
        }
        route_reasons = [
            "test_selected_mode"
            if selected_mode == "TEST_REVIEW"
            else "track_selected_mode"
            if selected_mode == "TRACK_DB"
            else "code_selected_mode"
            if selected_mode == "LS_CODE"
            else "ui_selected_mode"
        ]
    else:
        selected_mode = ""

    if selected_mode in {"UX_REVIEW", "LS_CODE"}:
        tools = get_code_readonly_tools()
    elif selected_mode == "TEST_REVIEW":
        tools = []
    elif selected_mode == "TRACK_DB":
        tools = get_track_readonly_tools()
    else:
        tools = get_available_readonly_tools()

    instructions = build_ls_elza_instructions()
    instructions += _general_ui_help_instruction(
        route,
        route_reasons,
        selected_mode,
    )
    if selected_mode == "UX_REVIEW":
        instructions += (
            "\n\nThe user explicitly selected persistent UX_REVIEW mode in the "
            "LocalSunoDb UI. Review the supplied current screen as a UX/help "
            "reviewer even if the question text alone would suggest another "
            "route. Do not use database tools. Use bounded source-inspection "
            "tools when they are needed to answer where, why, or how an actual "
            "LS control or behavior is implemented. A read-only inspection "
            "must end with a concrete explanation when the evidence supports "
            "one; it does not authorize any file or data change."
        )
    elif selected_mode == "TEST_REVIEW":
        instructions += (
            "\n\nThe user explicitly selected persistent TEST_REVIEW mode in "
            "the LocalSunoDb UI. Test the described function against the "
            "supplied current screenshot and read-only state. Give a strict "
            "PASS, FAIL, or UNCLEAR verdict using the TEST_REVIEW evidence "
            "rules, even if the question text alone suggests another route. "
            "Do not use database or source-code tools."
        )
    elif selected_mode == "TRACK_DB":
        instructions += (
            "\n\nThe user explicitly selected persistent TRACK_DB mode in "
            "the LocalSunoDb UI. Analyze exactly the one selected track. Use "
            "ls_track_summary and ls_local_family_status, then answer in this "
            "order: Suno data; local audio; Stems; Local family; data gaps; "
            "recommended next action. Do not use code tools, invent missing "
            "file details, or recommend controls and panel actions that are "
            "not explicitly confirmed by the supplied context or verified "
            "LocalSunoDb knowledge."
        )
    elif selected_mode == "LS_CODE":
        instructions += (
            "\n\nThe user explicitly selected persistent LS_CODE mode in the "
            "LocalSunoDb UI. Use the bounded source-inspection tools to answer "
            "questions about the actual running implementation. Begin with a "
            "targeted search and read only the relevant excerpt. State the "
            "verified cause or behavior in practical language. When useful, "
            "offer a concise Codex-ready repair prompt. Never edit files, run "
            "code or commands, create a release or ZIP, or claim that a "
            "proposed change was applied."
        )

    source_trace = []
    tool_names_used = []

    def execute_readonly_tool(call):
        tool_names_used.append(clean_text(getattr(call, "tool_id", "unknown"), 100))
        return _core_readonly_tool_result(call, source_trace)

    provider = OpenAIResponsesProvider(
        create_response=lambda provider_input, provider_instructions, provider_tools: (
            _create_openai_response(
                client,
                provider_input,
                provider_instructions,
                provider_tools,
            )
        )
    )
    tool_runtime = LSReadOnlyToolRuntime(handler=execute_readonly_tool)
    request = build_core_request(
        conversation_id=clean_text(conversation_id, 80) or "ls-elza",
        message=user_question,
        context=context if isinstance(context, dict) else {},
        tool_definitions=tools,
        provider_input=model_input,
        instructions=instructions,
    )

    response = ElzaCore(
        provider=provider,
        tool_runtime=tool_runtime,
    ).handle(request)

    provider_rounds = 0
    try:
        provider_rounds = int((response.metadata or {}).get("provider_rounds") or 0)
    except (TypeError, ValueError):
        provider_rounds = 0
    tool_rounds = max(0, provider_rounds - 1) if tool_names_used else 0

    if response.error is not None:
        error_code = clean_text(getattr(response.error, "code", ""), 100)
        if error_code in {
            "provider_tool_round_limit",
            "provider_tool_call_limit",
        }:
            _write_router_diagnostic(
                route,
                route_scores,
                route_reasons,
                user_question,
                tool_names_used,
                tool_rounds,
                len(tool_names_used),
                "tool_limit",
                selected_mode,
            )
            raise LSElzaError(
                "LS Elza exceeded the safe read-only tool-call limit.",
                status=502,
                code="readonly_tool_limit_reached",
            )
        _write_router_diagnostic(
            route,
            route_scores,
            route_reasons,
            user_question,
            tool_names_used,
            tool_rounds,
            len(tool_names_used),
            "core_error",
            selected_mode,
        )
        raise LSElzaError(
            clean_text(getattr(response.error, "message", ""), 1000)
            or "Elza Core could not complete the request.",
            status=502,
            code=error_code or "elza_core_request_failed",
        )

    _write_router_diagnostic(
        route,
        route_scores,
        route_reasons,
        user_question,
        tool_names_used,
        tool_rounds,
        len(tool_names_used),
        "answer",
        selected_mode,
    )
    return response, source_trace


def request_openai_answer(chat_id, user_text, context, images=None,
                          selected_mode=""):
    images = images if isinstance(images, list) else []
    with _HISTORY_LOCK:
        history = load_history_unlocked()
        chat = get_or_create_chat_unlocked(history, chat_id)
        resolved_chat_id = chat["id"]
        history_messages = build_api_history(chat.get("messages", []))
        save_history_unlocked(history)

    model_input = list(history_messages)
    current_text = (
        "Current read-only LocalSunoDb context:\n"
        + format_context_for_model(context)
        + "\n\nUser question:\n"
        + user_text
    )
    if images:
        current_content = [{"type": "input_text", "text": current_text}]
        for image in images:
            current_content.append({
                "type": "input_image",
                "image_url": (
                    "data:"
                    + image["mime_type"]
                    + ";base64,"
                    + image["data_base64"]
                ),
                "detail": image["detail"],
            })
        model_input.append({"role": "user", "content": current_content})
    else:
        model_input.append({"role": "user", "content": current_text})

    client = get_openai_client()

    try:
        response, source_trace = create_answer_response(
            client,
            model_input,
            selected_mode,
            conversation_id=resolved_chat_id,
            context=context,
        )
    except LSElzaError:
        raise
    except Exception as error:
        error_name = error.__class__.__name__
        if error_name == "AuthenticationError":
            message = "The OpenAI API key was rejected."
            code = "openai_authentication_failed"
            status = 401
        elif error_name == "RateLimitError":
            message = "The OpenAI API rate or usage limit was reached."
            code = "openai_rate_limit"
            status = 429
        elif error_name in {"APITimeoutError", "APIConnectionError"}:
            message = "The OpenAI API could not be reached."
            code = "openai_connection_failed"
            status = 502
        else:
            message = "The OpenAI API request failed."
            code = "openai_request_failed"
            status = 502
        raise LSElzaError(message, status=status, code=code) from error

    selection_request = extract_selection_request(source_trace)
    if selection_request is not None:
        return {
            "ok": True,
            "chat_id": resolved_chat_id,
            "selection_request": selection_request,
            "model": get_model_name(),
            "image_count": len(images),
            "sources": [],
        }

    answer = clean_text(
        getattr(response, "text", getattr(response, "output_text", "")),
        30000,
    )
    if not answer:
        raise LSElzaError(
            "The OpenAI API returned no text response.",
            status=502,
            code="openai_empty_response",
        )

    stored_user_text = user_text
    if images:
        stored_user_text += (
            "\n\n📎 Attēli šajā ziņā: "
            + str(len(images))
            + " (attēlu dati nav saglabāti)."
        )
    answer_sources = [{
        "id": "ls_context",
        "label": "LS Context",
        "kind": "provided",
        "detail": (
            "Šim pieprasījumam tika nodots pašreizējais LocalSunoDb "
            "read-only UI konteksts."
        ),
    }]
    if load_ls_elza_knowledge():
        answer_sources.append({
            "id": "ls_help",
            "label": "Help",
            "kind": "provided",
            "detail": (
                "Šim pieprasījumam bija pieejama pārbaudītā LS Help "
                "zināšanu bāze."
            ),
        })
    if images:
        answer_sources.append({
            "id": "image",
            "label": "Image" if len(images) == 1 else f"Images ×{len(images)}",
            "kind": "provided",
            "detail": (
                f"Šim pieprasījumam pievienoti attēli: {len(images)}. "
                "Attēlu dati sarunas vēsturē netiek saglabāti."
            ),
        })
    answer_sources.extend(_tool_answer_sources(source_trace))
    answer_sources = normalize_answer_sources(answer_sources)
    chat_payload = append_chat_exchange(
        resolved_chat_id,
        stored_user_text,
        answer,
        answer_sources,
    )
    chat_payload.update({
        "ok": True,
        "answer": answer,
        "model": get_model_name(),
        "image_count": len(images),
        "sources": answer_sources,
    })
    return chat_payload


def request_question_clarification(user_text, context):
    """Return a bounded clarification payload; caller persists the exchange."""
    instructions = (
        "Clarify one ambiguous LocalSunoDb user question. Return JSON only "
        "with string fields rewritten_question and explanation. Rewrite only "
        "when the supplied context supports one clear, non-destructive intent. "
        "The rewrite must be a complete question in the user's language and "
        "must not claim that an action was performed. If one safe rewrite is "
        "not possible, leave rewritten_question empty and briefly explain what "
        "specific information the user should add."
    )
    model_input = [{
        "role": "user",
        "content": (
            "Current read-only LocalSunoDb context:\n"
            + format_context_for_model(context)
            + "\n\nAmbiguous user question:\n"
            + user_text
        ),
    }]
    try:
        response = get_openai_client().responses.create(
            model=get_model_name(),
            instructions=instructions,
            input=model_input,
            store=False,
            max_output_tokens=700,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "ls_elza_question_clarification",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "rewritten_question": {"type": "string"},
                            "explanation": {"type": "string"},
                        },
                        "required": ["rewritten_question", "explanation"],
                        "additionalProperties": False,
                    },
                },
            },
        )
        raw_text = clean_text(getattr(response, "output_text", ""), 5000)
        if raw_text.startswith("```"):
            raw_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text, flags=re.I)
        payload = json.loads(raw_text)
        if not isinstance(payload, dict):
            raise ValueError("clarification response is not an object")
    except Exception as error:
        _write_router_diagnostic(
            "CLARIFY",
            {},
            ["ambiguous_goal_and_mode"],
            user_text,
            [],
            0,
            0,
            "clarification_failed",
        )
        error_name = error.__class__.__name__
        if error_name == "AuthenticationError":
            message = "The OpenAI API key was rejected."
            code = "openai_authentication_failed"
            status = 401
        elif error_name == "RateLimitError":
            message = "The OpenAI API rate or usage limit was reached."
            code = "openai_rate_limit"
            status = 429
        elif error_name in {"APITimeoutError", "APIConnectionError"}:
            message = "The OpenAI API could not be reached."
            code = "openai_connection_failed"
            status = 502
        else:
            message = "Elza could not clarify this question."
            code = "question_clarification_failed"
            status = 502
        raise LSElzaError(message, status=status, code=code) from error

    rewritten_question = clean_text(payload.get("rewritten_question"), MAX_USER_MESSAGE_CHARS)
    explanation = clean_text(payload.get("explanation"), 2000)
    if not rewritten_question and not explanation:
        explanation = (
            "Norādi, ko tieši vēlies noskaidrot un par kuru LocalSunoDb "
            "funkciju, skatu vai izvēlēto dziesmu ir jautājums."
        )
    _write_router_diagnostic(
        "CLARIFY",
        {},
        ["ambiguous_goal_and_mode"],
        user_text,
        [],
        0,
        0,
        "clarified" if rewritten_question else "needs_user_detail",
    )
    return {
        "ok": True,
        "clarification_required": bool(rewritten_question),
        "rewritten_question": rewritten_question,
        "explanation": explanation,
    }


# 9.  ------ Public service action -----

def handle_ls_elza_action(payload):
    if not isinstance(payload, dict):
        raise LSElzaError(
            "The LS Elza request must be a JSON object.",
            status=400,
            code="invalid_request",
        )

    action = clean_text(payload.get("action"), 40).lower() or "send"
    chat_id = clean_text(payload.get("chat_id"), 80)

    if action == "load":
        result = load_chat(chat_id)
        result["ok"] = True
        return result

    if action == "new_chat":
        result = create_new_chat()
        result["ok"] = True
        return result

    if action == "clear":
        result = clear_chat(chat_id)
        result["ok"] = True
        return result

    if action == "local_exchange":
        user_text = clean_text(payload.get("message"), MAX_USER_MESSAGE_CHARS)
        assistant_text = clean_text(payload.get("answer"), 30000)
        if not user_text or not assistant_text:
            raise LSElzaError(
                "Local exchange requires both user and assistant text.",
                status=400,
                code="invalid_local_exchange",
            )
        result = append_chat_exchange(
            chat_id,
            user_text,
            assistant_text,
            [{
                "id": "local",
                "label": "Local reply",
                "kind": "local",
                "detail": "Lokālā LS Elza atbilde saglabāta sarunas vēsturē.",
            }],
        )
        result.update({
            "ok": True,
            "answer": assistant_text,
            "model": "local",
            "image_count": 0,
        })
        return result

    if action == "clarify":
        user_text = clean_text(payload.get("message"), MAX_USER_MESSAGE_CHARS)
        if not user_text:
            raise LSElzaError(
                "Write a message before asking Elza to clarify it.",
                status=400,
                code="empty_message",
            )
        context = normalize_ls_context(payload.get("context"))
        clarification = request_question_clarification(user_text, context)
        rewritten = clean_text(
            clarification.get("rewritten_question"),
            MAX_USER_MESSAGE_CHARS,
        )
        explanation = clean_text(clarification.get("explanation"), 2000)
        if rewritten:
            assistant_text = (
                "Es sapratu jautājumu šādi: **" + rewritten + "**\n\n"
                "Pārbaudi formulējumu un nospied Send vēlreiz."
            )
        else:
            assistant_text = explanation or (
                "Norādi, ko tieši vēlies noskaidrot un par kuru LocalSunoDb "
                "funkciju, skatu vai izvēlēto dziesmu ir jautājums."
            )
        chat_payload = append_chat_exchange(
            chat_id,
            user_text,
            assistant_text,
            [{
                "id": "local",
                "label": "Question clarification",
                "kind": "local",
                "detail": "Jautājums un precizējums saglabāti sarunas vēsturē.",
            }],
        )
        chat_payload.update(clarification)
        chat_payload["answer"] = assistant_text
        return chat_payload

    if action != "send":
        raise LSElzaError(
            "Unknown LS Elza action.",
            status=400,
            code="unknown_action",
        )

    images = normalize_ls_images(payload.get("images"))
    selected_mode = clean_text(payload.get("selected_mode"), 40).upper()
    if selected_mode not in ALLOWED_SELECTED_MODES:
        raise LSElzaError(
            "Unknown LS Elza mode.",
            status=400,
            code="unknown_mode",
        )
    user_text = clean_text(payload.get("message"), MAX_USER_MESSAGE_CHARS)
    if not user_text and images:
        user_text = "Lūdzu, analizē pievienoto attēlu."
    if not user_text:
        raise LSElzaError(
            "Write a message before sending.",
            status=400,
            code="empty_message",
        )

    if not selected_mode and not images and is_simple_acknowledgement(user_text):
        answer = acknowledgement_answer(user_text)
        answer_sources = [{
            "id": "local",
            "label": "Local reply",
            "kind": "local",
            "detail": (
                "Īsā sarunas atbilde izveidota lokāli; OpenAI API un LS "
                "read-only rīki netika izsaukti."
            ),
        }]
        result = append_chat_exchange(
            chat_id,
            user_text,
            answer,
            answer_sources,
        )
        result.update({
            "ok": True,
            "answer": answer,
            "model": "local",
            "image_count": 0,
            "sources": answer_sources,
        })
        return result

    context = normalize_ls_context(payload.get("context"))
    if (
        selected_mode == "TRACK_DB"
        and len(context.get("selected_track_ids") or []) != 1
    ):
        raise LSElzaError(
            "Select exactly one track before using Track mode.",
            status=400,
            code="track_mode_requires_one_track",
        )
    with _SEND_LOCK:
        try:
            return request_openai_answer(
                chat_id,
                user_text,
                context,
                images,
                selected_mode,
            )
        except LSElzaError as error:
            failure_messages = {
                "openai_authentication_failed": "OpenAI API atslēga tika noraidīta.",
                "openai_rate_limit": "Sasniegts OpenAI API pieprasījumu vai lietojuma limits.",
                "openai_connection_failed": "OpenAI API pašlaik nav sasniedzams.",
                "openai_empty_response": "OpenAI API neatgrieza teksta atbildi.",
                "readonly_tool_limit_reached": "Read-only pārbaude sasniedza drošības limitu.",
            }
            assistant_text = failure_messages.get(
                error.code,
                "Elza nevarēja pabeigt šo pieprasījumu.",
            )
            result = append_chat_exchange(
                chat_id,
                user_text,
                assistant_text,
                [{
                    "id": "local",
                    "label": "Request status",
                    "kind": "local",
                    "detail": "Neizdevies pieprasījums saglabāts sarunas vēsturē.",
                }],
            )
            result.update({
                "ok": True,
                "answer": assistant_text,
                "model": "error",
                "image_count": len(images),
                "request_failed": True,
                "error_code": error.code,
            })
            return result


def error_payload(error):
    if isinstance(error, LSElzaError):
        return {
            "ok": False,
            "error": str(error),
            "error_code": error.code,
        }, error.status

    return {
        "ok": False,
        "error": "Unexpected LS Elza server error.",
        "error_code": "unexpected_error",
    }, 500
