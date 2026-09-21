# LS Elza semantic selection host bridge
# Created: 15.aug.2026   22:35
# Actual base: v5.425
# Purpose: Translate validated semantic selections to existing LS read-only filters
# ver. 1.1

"""Translate validated LS Elza semantic selections to host filter intents."""

from LS_Elza.locf_intent import recognize_locf_selection


def _clean_text(value, max_chars):
    text = str(value or "").strip()
    if len(text) > int(max_chars):
        text = text[: int(max_chars)].rstrip()
    return text


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

    try:
        exact_stem_count = int(request.get("exact_stem_count") or 0)
    except (TypeError, ValueError):
        return {"error": "Elza atgrieza nederīgu precīzo Stems skaitu."}
    if exact_stem_count < 0 or exact_stem_count > 100:
        return {"error": "Elza atgrieza neatbalstītu precīzo Stems skaitu."}
    if exact_stem_count and (filters or local_family_assigned is not None):
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

    if not filters and not exact_stem_count and local_family_assigned is None:
        return {"error": "Elza neatrada nevienu droši izpildāmu LS atlases nosacījumu."}

    return result


def prepare_local_locf_service_result(payload):
    """Return a service-compatible local selection only for clear simple LocF commands."""
    if not isinstance(payload, dict):
        return None
    if str(payload.get("action") or "send").strip().lower() != "send":
        return None
    if payload.get("images"):
        return None
    if str(payload.get("selected_mode") or "").strip():
        return None
    selection_request = recognize_locf_selection(payload.get("message"))
    if selection_request is None:
        return None
    return {
        "ok": True,
        "chat_id": str(payload.get("chat_id") or "").strip(),
        "selection_request": selection_request,
        "model": "local-readonly",
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
