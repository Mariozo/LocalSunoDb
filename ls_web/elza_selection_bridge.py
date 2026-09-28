# LS Elza semantic selection host bridge
# Created: 15.aug.2026   22:35
# Actual base: v5.425
# Purpose: Translate validated semantic selections to existing LS read-only filters
# ver. 1.1

"""Translate validated LS Elza semantic selections to host filter intents."""

import re
import unicodedata

from LS_Elza.locf_intent import recognize_locf_selection


def _clean_text(value, max_chars):
    text = str(value or "").strip()
    if len(text) > int(max_chars):
        text = text[: int(max_chars)].rstrip()
    return text




_ALL_TEXT_FIELDS = ["name", "track_id", "lyrics", "prompt", "tags"]


def _fold_user_text(value):
    text = re.sub(r"\s+", " ", str(value or "").strip().casefold())
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )


def _has_selection_command(plain):
    return bool(re.search(
        r"\b(?:parad\w*|atlas\w*|atrod\w*|atrast\w*|mekl\w*|"
        r"uzskait\w*|atver\w*|show|find|list|open)\b",
        plain,
    ))


def _extract_text_query(source):
    quoted = re.search(r'["“”]([^"“”]{1,160})["“”]', source)
    if quoted:
        return re.sub(r"\s+", " ", quoted.group(1).strip())
    named = re.search(
        r"\b(?:vārds?|vārdu|frāze|fraze|word)\s+"
        r'["“”]?([^\s,;:.!?"“”]{1,120})',
        source,
        flags=re.IGNORECASE,
    )
    return named.group(1).strip() if named else ""


def _requested_text_fields(plain):
    if (
        re.search(r"\b(?:jebkur|citur|elsewhere|anywhere|visur)\b", plain)
        or re.search(r"\bkaut\s+kur\b", plain)
        or re.search(r"\bkad[aā]\s+cit[aā]\s+lauk[aā]\b", plain)
    ):
        return list(_ALL_TEXT_FIELDS)

    fields = []
    if re.search(r"\b(?:nosaukum\w*|name|title)\b", plain):
        fields.append("name")
    if re.search(r"\btrack\s*id\b", plain):
        fields.append("track_id")
    if re.search(r"\b(?:lyrics?|dziesm\w*\s+tekst\w*|tekst\w*)\b", plain):
        fields.append("lyrics")
    if re.search(r"\bprompt\w*\b", plain):
        fields.append("prompt")
    if re.search(r"(?:^|\s)#?tag\w*\b", plain):
        fields.append("tags")
    return fields


def _text_field_label(field):
    return {
        "name": "Name",
        "track_id": "Track ID",
        "lyrics": "Lyrics",
        "prompt": "Prompt",
        "tags": "Tags",
    }.get(field, field)


def _recognize_local_text_selection(message):
    source = re.sub(r"\s+", " ", str(message or "").strip())
    plain = _fold_user_text(source)
    if not source or not _has_selection_command(plain):
        return None
    if re.search(r"\blocf\b|\blocal\s+family\b", plain):
        return None

    text_query = _extract_text_query(source)
    text_fields = _requested_text_fields(plain)
    if not text_query or not text_fields:
        return None

    local_audio = ""
    if (
        re.search(r"\b(?:vietej\w*|lokal\w*)\b", plain)
        and re.search(
            r"\b(?:dziesm\w*|ierakst\w*|audio\w*|wav\w*|fail\w*|track\w*)\b",
            plain,
        )
    ):
        local_audio = "with"

    return {
        "safe_to_execute": True,
        "reason": "",
        "category": "",
        "kind_filter": "",
        "local_audio": local_audio,
        "local_audio_extensions": ["wav"] if re.search(r"\bwav\b", plain) else [],
        "exclude_ui_types": [],
        "flags": [],
        "any_flag": False,
        "exact_flags": False,
        "tags": [],
        "workspace": "",
        "local_family": "",
        "local_family_assigned": None,
        "title_query": "",
        "anywhere_query": (
            text_query if set(text_fields) == set(_ALL_TEXT_FIELDS) else ""
        ),
        "text_query": text_query,
        "text_fields": text_fields,
        "exact_stem_count": 0,
    }


def build_host_selection_intent(
    request,
    *,
    resolve_workspace,
    resolve_local_family,
    normalize_tags,
):
    if not isinstance(request, dict):
        return {"error": "Elza neatgrieza derīgu atlases aprakstu."}

    if not bool(request.get("safe_to_execute")):
        reason = _clean_text(request.get("reason"), 600)
        return {"error": reason or "Elza nevarēja droši noteikt visus atlases nosacījumus."}

    filters = {}
    labels = []

    category = _clean_text(request.get("category"), 40)
    if category:
        if category not in {"Song", "Instrumental"}:
            return {"error": "Elza atgrieza neatbalstītu kategoriju."}
        filters["category_filter"] = category
        labels.append(category)

    kind_filter = _clean_text(request.get("kind_filter"), 40)
    if kind_filter:
        kind_map = {
            "liked": ("__liked__", "Liked"),
            "has_stems": ("__has_stems__", "Has Stems"),
        }
        if kind_filter not in kind_map:
            return {"error": "Elza atgrieza neatbalstītu LS tipa filtru."}
        filters["kind_filter"], label = kind_map[kind_filter]
        labels.append(label)

    local_audio = _clean_text(request.get("local_audio"), 40)
    if local_audio:
        if local_audio not in {"with", "without"}:
            return {"error": "Elza atgrieza neatbalstītu lokālā audio filtru."}
        filters["local_audio_filter"] = local_audio
        labels.append("With local audio" if local_audio == "with" else "No local audio")

    raw_extensions = request.get("local_audio_extensions") or []
    if not isinstance(raw_extensions, list):
        return {"error": "Elza atgrieza nederīgu lokālā audio formātu atlasi."}
    allowed_extensions = {"wav", "mp3", "flac", "m4a", "aac", "ogg"}
    local_audio_extensions = []
    for item in raw_extensions:
        extension = _clean_text(item, 20).lower().lstrip(".")
        if not extension or extension not in allowed_extensions:
            return {"error": "Elza atgrieza neatbalstītu lokālā audio formātu."}
        if extension not in local_audio_extensions:
            local_audio_extensions.append(extension)
    if local_audio_extensions:
        if local_audio == "without":
            return {
                "error": (
                    "Konkrētu lokālā audio formātu nevar apvienot ar nosacījumu "
                    "“bez lokālā audio”."
                )
            }
        filters["local_audio_filter"] = "with"
        labels = [label for label in labels if label != "With local audio"]
        labels.append(
            "Local " + "/".join(extension.upper() for extension in local_audio_extensions)
        )

    raw_excluded_types = request.get("exclude_ui_types") or []
    if not isinstance(raw_excluded_types, list):
        return {"error": "Elza atgrieza nederīgu izslēdzamo LS Type sarakstu."}
    exclude_ui_types = []
    seen_excluded_types = set()
    for item in raw_excluded_types[:20]:
        ui_type = _clean_text(item, 120)
        key = ui_type.casefold()
        if ui_type and key not in seen_excluded_types:
            exclude_ui_types.append(ui_type)
            seen_excluded_types.add(key)
    for ui_type in exclude_ui_types:
        labels.append(f"Bez Type: {ui_type}")

    raw_flags = request.get("flags")
    if not isinstance(raw_flags, list):
        return {"error": "Elza atgrieza nederīgu Flags atlasi."}
    flags = []
    for item in raw_flags:
        try:
            number = int(item)
        except (TypeError, ValueError):
            return {"error": "Elza atgrieza nederīgu Flag numuru."}
        if number not in {1, 2, 3, 4, 5}:
            return {"error": "Elza atgrieza neatbalstītu Flag numuru."}
        if number not in flags:
            flags.append(number)
    flags.sort()

    any_flag = bool(request.get("any_flag"))
    exact_flags = bool(request.get("exact_flags"))
    if any_flag and flags:
        return {"error": "Any Flag nevar droši apvienot ar konkrētiem Flags."}
    if exact_flags and not flags:
        return {"error": "Precīzai Flags atlasei nav norādīts neviens Flag."}

    if flags:
        masks = [1 << (number - 1) for number in flags]
        filters["flag_filter"] = ",".join(str(mask) for mask in masks)
        if exact_flags:
            labels.append("Tieši " + " + ".join(f"Flag {number}" for number in flags))
        else:
            labels.extend([f"{number}+*" for number in flags])
    elif any_flag:
        filters["search_marks"] = True
        labels.append("Any Flag")

    raw_tags = request.get("tags")
    if not isinstance(raw_tags, list):
        return {"error": "Elza atgrieza nederīgu tagu atlasi."}
    tags = normalize_tags(raw_tags)
    if tags:
        filters["tag_filter"] = ",".join(tags)
        labels.extend(tags)

    workspace_request = _clean_text(request.get("workspace"), 300)
    if workspace_request:
        workspace = resolve_workspace(workspace_request)
        if not workspace:
            return {"error": f"Workspace “{workspace_request}” LS datubāzē nav atrasts."}
        filters["workspace"] = workspace
        labels.append(f"Workspace: {workspace}")

    local_family_assigned = request.get("local_family_assigned")
    if local_family_assigned is not None and not isinstance(local_family_assigned, bool):
        return {"error": "Elza atgrieza nederīgu LocF piesaistes stāvokli."}

    family_request = _clean_text(request.get("local_family"), 300)
    if family_request and local_family_assigned is False:
        return {"error": "Konkrētu Local Family nevar apvienot ar nosacījumu bez LocF."}
    if family_request:
        family = resolve_local_family(family_request)
        if not family:
            return {"error": f"Apstiprināta Local family “{family_request}” nav atrasta."}
        filters["local_family_filter"] = family
        labels.append(f"Local family: {family}")
    if local_family_assigned is True:
        labels.append("LocF")
    elif local_family_assigned is False:
        labels.append("No LocF")

    title_query = _clean_text(request.get("title_query"), 300)
    if title_query:
        filters["query"] = title_query
        filters["search_name"] = True
        labels.append(f"Name: {title_query}")

    anywhere_query = _clean_text(request.get("anywhere_query"), 300)
    text_query = _clean_text(request.get("text_query"), 300) or anywhere_query
    raw_text_fields = request.get("text_fields") or []
    if not isinstance(raw_text_fields, list):
        return {"error": "Elza atgrieza nederīgu teksta meklēšanas lauku sarakstu."}
    text_fields = []
    for item in raw_text_fields[:5]:
        field = _clean_text(item, 20).lower()
        if field not in set(_ALL_TEXT_FIELDS):
            return {"error": "Elza atgrieza neatbalstītu teksta meklēšanas lauku."}
        if field not in text_fields:
            text_fields.append(field)
    if anywhere_query and not text_fields:
        text_fields = list(_ALL_TEXT_FIELDS)
    if text_query and text_fields:
        if set(text_fields) == set(_ALL_TEXT_FIELDS):
            labels.append(f"Anywhere: {text_query}")
        elif text_fields == ["name"]:
            labels.append(f"Name: {text_query}")
        elif text_fields == ["prompt"]:
            labels.append(f"Prompt: {text_query}")
        elif text_fields == ["lyrics"]:
            labels.append(f"Lyrics: {text_query}")
        elif text_fields == ["tags"]:
            labels.append(f"Tags: {text_query}")
        elif text_fields == ["track_id"]:
            labels.append(f"Track ID: {text_query}")
        else:
            labels.append(
                " + ".join(_text_field_label(field) for field in text_fields)
                + f": {text_query}"
            )

    try:
        exact_stem_count = int(request.get("exact_stem_count") or 0)
    except (TypeError, ValueError):
        return {"error": "Elza atgrieza nederīgu precīzo Stems skaitu."}
    if exact_stem_count < 0 or exact_stem_count > 100:
        return {"error": "Elza atgrieza neatbalstītu precīzo Stems skaitu."}
    if exact_stem_count and (
        filters
        or local_audio_extensions
        or exclude_ui_types
        or local_family_assigned is not None
        or bool(text_query)
    ):
        return {
            "error": (
                "Precīzu Stems skaitu pašreizējā drošajā atlasē nevar apvienot "
                "ar citiem filtriem."
            )
        }

    result = {
        "filters": filters,
        "labels": labels,
        "summary": " + ".join(labels) or "LS selection",
        "save_name": (" + ".join(labels) or "LS Elza selection")[:80],
        "local_family_assigned": local_family_assigned,
        "local_audio_extensions": local_audio_extensions,
        "exclude_ui_types": exclude_ui_types,
        "anywhere_query": anywhere_query,
        "text_query": text_query,
        "text_fields": text_fields,
    }

    if exact_flags:
        exact_flag_mask = 0
        for number in flags:
            exact_flag_mask |= 1 << (number - 1)
        result["exact_flag_mask"] = exact_flag_mask

    if exact_stem_count:
        result["exact_stem_count"] = exact_stem_count
        result["summary"] = f"Tieši {exact_stem_count} Stems"
        result["save_name"] = result["summary"]

    if (
        not filters
        and not exact_stem_count
        and not exclude_ui_types
        and local_family_assigned is None
        and not text_query
    ):
        return {"error": "Elza neatrada nevienu droši izpildāmu LS atlases nosacījumu."}

    return result


def prepare_local_locf_service_result(payload):
    """Return a deterministic local text selection first, then explicit LocF."""
    if not isinstance(payload, dict):
        return None
    if str(payload.get("action") or "send").strip().lower() != "send":
        return None
    if payload.get("images"):
        return None
    if str(payload.get("selected_mode") or "").strip():
        return None
    message = payload.get("message")
    selection_request = _recognize_local_text_selection(message)
    model_name = "local-readonly-text-v240"
    if selection_request is None:
        plain = _fold_user_text(message)
        if not re.search(r"\blocf\b|\blocal\s+family\b", plain):
            return None
        selection_request = recognize_locf_selection(message)
        model_name = "local-readonly-locf-v240"
    if selection_request is None:
        return None
    return {
        "ok": True,
        "chat_id": str(payload.get("chat_id") or "").strip(),
        "selection_request": selection_request,
        "model": model_name,
        "image_count": 0,
        "sources": [],
    }


def finalize_semantic_selection(
    payload,
    service_result,
    *,
    resolve_workspace,
    resolve_local_family,
    normalize_tags,
    get_selection_result,
    get_exact_stem_result,
    build_answer,
    append_chat_exchange,
    get_locf_selection_result=None,
):
    payload = payload if isinstance(payload, dict) else {}
    service_result = service_result if isinstance(service_result, dict) else {}
    request = service_result.get("selection_request")
    intent = build_host_selection_intent(
        request,
        resolve_workspace=resolve_workspace,
        resolve_local_family=resolve_local_family,
        normalize_tags=normalize_tags,
    )

    query_result = None
    if intent.get("error"):
        answer = str(intent.get("error") or "Elza nevarēja droši sagatavot atlasi.")
        source = {
            "id": "local",
            "label": "Selection validation",
            "kind": "local",
            "detail": "Atlases nosacījumi netika izpildīti, jo validācija neizdevās.",
        }
    else:
        assignment_state = intent.get("local_family_assigned")
        if assignment_state is not None:
            if not callable(get_locf_selection_result):
                answer = "LocF lokālā atlase pašlaik nav pieejama."
                source = {
                    "id": "local",
                    "label": "Selection validation",
                    "kind": "local",
                    "detail": "LocF lokālās atlases izpildītājs nav pieejams.",
                }
            else:
                query_result = get_locf_selection_result(
                    bool(assignment_state),
                    intent,
                    limit=20,
                )
                answer = build_answer(query_result)
                source = {
                    "id": "db",
                    "label": "DB read-only",
                    "kind": "consulted",
                    "detail": (
                        "LocF atlase tika izpildīta no apstiprinātās Track ID uz "
                        "Local Family piesaistes kartes."
                    ),
                }
        else:
            if intent.get("exact_stem_count") is not None:
                query_result = get_exact_stem_result(int(intent["exact_stem_count"]))
            else:
                query_result = get_selection_result(intent, limit=20)
            answer = build_answer(query_result)
            source = {
                "id": "db",
                "label": "DB read-only",
                "kind": "consulted",
                "detail": (
                    "Elzas semantiski saprastie atlases nosacījumi tika validēti un "
                    "izpildīti ar esošo LS read-only filtru loģiku."
                ),
            }

    chat_id = str(service_result.get("chat_id") or payload.get("chat_id") or "").strip()
    user_text = str(payload.get("message") or "").strip()
    if callable(append_chat_exchange):
        chat_payload = append_chat_exchange(chat_id, user_text, answer, [source])
    else:
        chat_payload = {"chat_id": chat_id}
    if not isinstance(chat_payload, dict):
        chat_payload = {"chat_id": chat_id}

    response_update = {
        "ok": True,
        "answer": answer,
        "model": str(service_result.get("model") or ""),
        "image_count": int(service_result.get("image_count") or 0),
        "sources": [{
            "id": source["id"],
            "label": source["label"],
            "kind": source["kind"],
        }],
    }

    if query_result is not None and int(query_result.get("matched_count") or 0) > 0:
        if query_result.get("single_track"):
            response_update.update({
                "ls_view_url": query_result.get("view_url"),
                "ls_view_label": "Atvērt dziesmu LS",
            })
        else:
            response_update.update({
                "ls_view_url": query_result.get("view_url"),
                "ls_view_label": "Atvērt atlasi LS",
            })
            if query_result.get("save_view_supported", True):
                response_update.update({
                    "ls_save_view_url": query_result.get("view_url"),
                    "ls_save_view_name": query_result.get("save_name"),
                    "ls_save_view_label": "Saglabāt kā View",
                })

    chat_payload.update(response_update)
    return chat_payload


def prepare_selection_transport(payload):
    payload = dict(payload) if isinstance(payload, dict) else {}
    action = str(payload.get("action") or "send").strip().lower()
    query_id = str(payload.get("query_id") or "").strip().lower()
    use_legacy_local = (
        action == "local_readonly"
        and query_id == "liked_without_local_audio"
    )
    if action == "local_readonly" and not use_legacy_local:
        payload["action"] = "send"
        payload["selected_mode"] = ""
    return payload, use_legacy_local
