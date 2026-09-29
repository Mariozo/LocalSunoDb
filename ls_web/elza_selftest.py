"""Read-only runtime regression matrix for LS Elza selection semantics."""

from __future__ import annotations

import re
import unicodedata
import urllib.parse

from ls_data.repository import (
    get_canonical_connection,
    get_confirmed_local_family_filter_options,
)


SELFTEST_SUITE_VERSION = 2


def _fold(value):
    text = re.sub(r"\s+", " ", str(value or "").strip().casefold())
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )


def _base_request(**changes):
    request = {
        "safe_to_execute": True,
        "reason": "",
        "category": "",
        "flags": [],
        "exact_flags": False,
        "any_flag": False,
        "kind_filter": "",
        "local_audio": "",
        "tags": [],
        "workspace": "",
        "local_family": "",
        "local_family_assigned": None,
        "title_query": "",
        "exact_stem_count": 0,
        "local_audio_extensions": [],
        "wav_scope": "",
        "exclude_ui_types": [],
        "include_ui_types": [],
        "minimum_flag_count": 0,
        "anywhere_query": "",
        "text_query": "",
        "text_fields": [],
    }
    request.update(changes)
    return request


def _row_value(row, key, default=""):
    try:
        value = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if value is None else value


def _load_facts():
    conn = get_canonical_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                t.id,
                COALESCE(t.title, '') AS title,
                COALESCE(t.prompt, '') AS prompt,
                COALESCE(t.lyrics, '') AS lyrics,
                COALESCE(t.source_type, '') AS source_type,
                COALESCE(t.source_task, '') AS source_task,
                COALESCE(t.kind, '') AS kind,
                COALESCE(t.audio_url, '') AS audio_url,
                COALESCE(t.is_liked, 0) AS is_liked,
                COALESCE(u.marks, 0) AS user_marks,
                COALESCE(u.tags, '') AS user_tags,
                COALESCE(u.manual_category, '') AS manual_category,
                CASE WHEN EXISTS (
                    SELECT 1
                    FROM main.track_variants tv
                    JOIN main.media_files mf ON mf.variant_id = tv.id
                    WHERE tv.track_id = t.id
                      AND mf.role = 'main'
                ) THEN 1 ELSE 0 END AS has_local_audio,
                CASE WHEN EXISTS (
                    SELECT 1
                    FROM main.track_variants tv
                    JOIN main.media_files mf ON mf.variant_id = tv.id
                    WHERE tv.track_id = t.id
                      AND mf.role = 'main'
                      AND lower(mf.format) = 'wav'
                ) THEN 1 ELSE 0 END AS has_wav,
                CASE WHEN EXISTS (
                    SELECT 1
                    FROM main.track_variants tv
                    JOIN main.media_files mf ON mf.variant_id = tv.id
                    WHERE tv.track_id = t.id
                      AND mf.role = 'main'
                      AND lower(mf.format) = 'mp3'
                ) THEN 1 ELSE 0 END AS has_mp3,
                CASE WHEN EXISTS (
                    SELECT 1
                    FROM main.track_variants tv
                    JOIN main.media_files mf ON mf.variant_id = tv.id
                    WHERE tv.track_id = t.id
                      AND mf.role = 'stem'
                ) THEN 1 ELSE 0 END AS has_stems
            FROM main.tracks t
            LEFT JOIN main.track_user u ON u.track_id = t.id
            WHERE IFNULL(t.library_status, 'active') = 'active'
              AND IFNULL(t.finder_hidden, 0) != 1
              AND IFNULL(t.kind, '') != 'Stem'
            ORDER BY lower(t.id)
            """
        ).fetchall()
    finally:
        conn.close()

    facts = []
    for row in rows:
        try:
            marks = int(_row_value(row, "user_marks", 0) or 0)
        except (TypeError, ValueError):
            marks = 0
        marks = max(0, min(31, marks))
        kind = str(_row_value(row, "kind", "") or "").strip()
        manual_category = str(
            _row_value(row, "manual_category", "") or ""
        ).strip()
        main_category = manual_category or (
            kind if kind in {"Song", "Instrumental", "SongOrInstrumental"} else ""
        )
        type_keys = {
            str(_row_value(row, "source_type", "") or "").strip().casefold(),
            str(_row_value(row, "source_task", "") or "").strip().casefold(),
            kind.casefold(),
        }
        type_keys.discard("")
        facts.append({
            "id": str(_row_value(row, "id", "") or "").strip(),
            "title": str(_row_value(row, "title", "") or ""),
            "prompt": str(_row_value(row, "prompt", "") or ""),
            "lyrics": str(_row_value(row, "lyrics", "") or ""),
            "tags": str(_row_value(row, "user_tags", "") or ""),
            "type_keys": type_keys,
            "liked": bool(int(_row_value(row, "is_liked", 0) or 0)),
            "marks": marks,
            "main_category": main_category,
            "has_local_audio": bool(int(_row_value(row, "has_local_audio", 0) or 0)),
            "has_suno_audio": bool(str(_row_value(row, "audio_url", "") or "").strip()),
            "has_wav": bool(int(_row_value(row, "has_wav", 0) or 0)),
            "has_mp3": bool(int(_row_value(row, "has_mp3", 0) or 0)),
            "has_stems": bool(int(_row_value(row, "has_stems", 0) or 0)),
        })
    return facts


def _track_ids_from_view_url(value):
    url = str(value or "").strip()
    if not url:
        return None
    parsed = urllib.parse.urlparse(url)
    raw = urllib.parse.parse_qs(parsed.query).get("track_ids", [])
    if not raw:
        return None
    return {
        item.strip().casefold()
        for item in raw[0].split(",")
        if item.strip()
    }


def _expected_ids(facts, predicate):
    return {
        str(item["id"]).casefold()
        for item in facts
        if item.get("id") and predicate(item)
    }


def _type_is_upload(item):
    return "upload" in set(item.get("type_keys") or set())


def _marks_at_least(item, count):
    return (int(item.get("marks") or 0) & 31).bit_count() >= int(count)


def _required_flags(item, numbers):
    mask = 0
    for number in numbers:
        mask |= 1 << (int(number) - 1)
    marks = int(item.get("marks") or 0) & 31
    return (marks & mask) == mask


def _probe_token(facts, fields):
    token_counts = {}
    for item in facts:
        values = [_fold(item.get(field, "")) for field in fields]
        seen = set()
        for value in values:
            for token in re.findall(r"[a-z0-9]{4,}", value):
                if token in seen:
                    continue
                seen.add(token)
                token_counts[token] = token_counts.get(token, 0) + 1
    if not token_counts:
        return ""
    return min(
        token_counts,
        key=lambda token: (token_counts[token], -len(token), token),
    )


def _actual_for_request(request):
    from ls_web import elza_adapter
    from ls_web import elza_selection_bridge

    intent = elza_selection_bridge.build_host_selection_intent(
        request,
        resolve_workspace=lambda value: value,
        resolve_local_family=lambda value: value,
        normalize_tags=lambda values: list(values or []),
    )
    if "error" in intent:
        return {"error": str(intent.get("error") or "selection intent error")}
    result = elza_adapter.get_ls_elza_selection_result(intent, limit=50)
    return {
        "count": int(result.get("matched_count") or 0),
        "ids": _track_ids_from_view_url(result.get("view_url")),
        "summary": str(result.get("summary") or ""),
    }


def _actual_for_locf(assigned):
    from ls_web.elza_locf import get_locf_selection_result

    result = get_locf_selection_result(
        bool(assigned),
        {
            "filters": {},
            "summary": "LocF" if assigned else "No LocF",
            "save_name": "LocF" if assigned else "No LocF",
        },
        limit=50,
    )
    return {
        "count": int(result.get("matched_count") or 0),
        "ids": _track_ids_from_view_url(result.get("view_url")) or set(),
        "summary": str(result.get("summary") or ""),
    }


def _case_result(case_id, expected_ids, actual, *, compare_ids=True):
    expected_ids = {str(item).casefold() for item in expected_ids}
    if isinstance(actual, dict) and actual.get("error"):
        return {
            "id": case_id,
            "status": "FAIL",
            "expected_count": len(expected_ids),
            "actual_count": None,
            "problem": str(actual.get("error") or "selection execution failed"),
        }

    actual_count = int((actual or {}).get("count") or 0)
    expected_count = len(expected_ids)
    actual_ids = (actual or {}).get("ids")
    count_ok = actual_count == expected_count
    ids_ok = True
    missing = []
    extra = []
    if compare_ids and actual_ids is not None:
        actual_ids = {str(item).casefold() for item in actual_ids}
        ids_ok = actual_ids == expected_ids
        missing = sorted(expected_ids - actual_ids)[:3]
        extra = sorted(actual_ids - expected_ids)[:3]

    status = "PASS" if count_ok and ids_ok else "FAIL"
    result = {
        "id": case_id,
        "status": status,
        "expected_count": expected_count,
        "actual_count": actual_count,
    }
    if status == "FAIL":
        problem = []
        if not count_ok:
            problem.append("count mismatch")
        if not ids_ok:
            problem.append("Track ID set mismatch")
        result["problem"] = "; ".join(problem)
        if missing:
            result["missing_sample"] = missing
        if extra:
            result["extra_sample"] = extra
    return result


def _engine_cases(facts):
    active_ids = {str(item["id"]).casefold() for item in facts if item.get("id")}
    cases = []

    specs = [
        (
            "local_liked_min3",
            _base_request(
                local_audio="with",
                kind_filter="liked",
                minimum_flag_count=3,
            ),
            lambda item: (
                item["has_local_audio"] and item["liked"] and _marks_at_least(item, 3)
            ),
            True,
        ),
        (
            "wav_upload_all",
            _base_request(
                wav_scope="all",
                include_ui_types=["Upload"],
            ),
            lambda item: (
                (item["has_suno_audio"] or item["has_wav"])
                and _type_is_upload(item)
            ),
            True,
        ),
        (
            "local_wav_upload",
            _base_request(
                wav_scope="local",
                local_audio_extensions=["wav"],
                include_ui_types=["Upload"],
            ),
            lambda item: item["has_wav"] and _type_is_upload(item),
            True,
        ),
        (
            "wav_without_upload",
            _base_request(
                wav_scope="local",
                local_audio_extensions=["wav"],
                exclude_ui_types=["Upload"],
            ),
            lambda item: item["has_wav"] and not _type_is_upload(item),
            True,
        ),
        (
            "upload_only",
            _base_request(include_ui_types=["Upload"]),
            _type_is_upload,
            True,
        ),
        (
            "without_upload_min1",
            _base_request(
                exclude_ui_types=["Upload"],
                minimum_flag_count=1,
            ),
            lambda item: (not _type_is_upload(item)) and _marks_at_least(item, 1),
            True,
        ),
        (
            "local_min1",
            _base_request(local_audio="with", minimum_flag_count=1),
            lambda item: item["has_local_audio"] and _marks_at_least(item, 1),
            True,
        ),
        (
            "local_min5",
            _base_request(local_audio="with", minimum_flag_count=5),
            lambda item: item["has_local_audio"] and _marks_at_least(item, 5),
            True,
        ),
        (
            "liked_min2",
            _base_request(kind_filter="liked", minimum_flag_count=2),
            lambda item: item["liked"] and _marks_at_least(item, 2),
            True,
        ),
        (
            "exact_flag3",
            _base_request(flags=[3], exact_flags=True),
            lambda item: int(item["marks"]) == 4,
            True,
        ),
        (
            "flags1_and3",
            _base_request(flags=[1, 3]),
            lambda item: _required_flags(item, [1, 3]),
            False,
        ),
        (
            "any_flag",
            _base_request(any_flag=True),
            lambda item: int(item["marks"]) != 0,
            False,
        ),
        (
            "no_local_min1",
            _base_request(local_audio="without", minimum_flag_count=1),
            lambda item: (not item["has_local_audio"]) and _marks_at_least(item, 1),
            True,
        ),
        (
            "song_min1",
            _base_request(category="Song", minimum_flag_count=1),
            lambda item: item["main_category"] == "Song" and _marks_at_least(item, 1),
            True,
        ),
        (
            "instrumental_min1",
            _base_request(category="Instrumental", minimum_flag_count=1),
            lambda item: (
                item["main_category"] == "Instrumental"
                and _marks_at_least(item, 1)
            ),
            True,
        ),
        (
            "has_stems_min1",
            _base_request(kind_filter="has_stems", minimum_flag_count=1),
            lambda item: item["has_stems"] and _marks_at_least(item, 1),
            True,
        ),
    ]

    for case_id, request, predicate, compare_ids in specs:
        expected = _expected_ids(facts, predicate)
        cases.append(
            _case_result(
                case_id,
                expected,
                _actual_for_request(request),
                compare_ids=compare_ids,
            )
        )

    mapped = set()
    try:
        for family in get_confirmed_local_family_filter_options():
            if not isinstance(family, dict):
                continue
            for track_id in family.get("track_ids") or []:
                key = str(track_id or "").strip().casefold()
                if key:
                    mapped.add(key)
    except Exception:
        mapped = set()

    cases.append(
        _case_result(
            "locf_assigned",
            active_ids.intersection(mapped),
            _actual_for_locf(True),
            compare_ids=True,
        )
    )
    cases.append(
        _case_result(
            "locf_unassigned",
            active_ids.difference(mapped),
            _actual_for_locf(False),
            compare_ids=True,
        )
    )

    name_token = _probe_token(facts, ["title"])
    if name_token:
        expected = _expected_ids(
            facts,
            lambda item: name_token in _fold(item.get("title", "")),
        )
        cases.append(
            _case_result(
                "name_probe",
                expected,
                _actual_for_request(
                    _base_request(
                        text_query=name_token,
                        text_fields=["name"],
                    )
                ),
                compare_ids=True,
            )
        )
    else:
        cases.append({
            "id": "name_probe",
            "status": "UNCLEAR",
            "problem": "DB nav piemērota Name testa tokena.",
        })

    prompt_token = _probe_token(facts, ["prompt"])
    if prompt_token:
        expected = _expected_ids(
            facts,
            lambda item: prompt_token in _fold(item.get("prompt", "")),
        )
        cases.append(
            _case_result(
                "prompt_probe",
                expected,
                _actual_for_request(
                    _base_request(
                        text_query=prompt_token,
                        text_fields=["prompt"],
                    )
                ),
                compare_ids=True,
            )
        )
    else:
        cases.append({
            "id": "prompt_probe",
            "status": "UNCLEAR",
            "problem": "DB nav piemērota Prompt testa tokena.",
        })

    anywhere_fields = ["title", "id", "lyrics", "prompt", "tags"]
    anywhere_token = _probe_token(facts, anywhere_fields)
    if anywhere_token:
        expected = _expected_ids(
            facts,
            lambda item: any(
                anywhere_token in _fold(item.get(field, ""))
                for field in anywhere_fields
            ),
        )
        cases.append(
            _case_result(
                "anywhere_probe",
                expected,
                _actual_for_request(
                    _base_request(
                        anywhere_query=anywhere_token,
                        text_query=anywhere_token,
                        text_fields=["name", "track_id", "lyrics", "prompt", "tags"],
                    )
                ),
                compare_ids=True,
            )
        )
    else:
        cases.append({
            "id": "anywhere_probe",
            "status": "UNCLEAR",
            "problem": "DB nav piemērota Anywhere testa tokena.",
        })

    return cases


def _value_matches(actual, expected):
    if isinstance(expected, list):
        return list(actual or []) == expected
    return actual == expected


def _parser_case(case_id, message, expected):
    from ls_web.elza_selection_bridge import prepare_local_locf_service_result

    service_result = prepare_local_locf_service_result({
        "action": "send",
        "message": message,
        "selected_mode": "",
        "images": [],
    })
    request = (
        service_result.get("selection_request")
        if isinstance(service_result, dict)
        else None
    )
    if not isinstance(request, dict):
        return {
            "id": case_id,
            "status": "FAIL",
            "problem": "Deterministiskais parseris neatpazina pieprasījumu.",
        }
    mismatches = []
    for key, expected_value in expected.items():
        actual_value = request.get(key)
        if not _value_matches(actual_value, expected_value):
            mismatches.append(
                f"{key}: expected {expected_value!r}, got {actual_value!r}"
            )
    return {
        "id": case_id,
        "status": "PASS" if not mismatches else "FAIL",
        **({"problem": "; ".join(mismatches[:3])} if mismatches else {}),
    }


def _parser_cases():
    return [
        _parser_case(
            "parser_local_like_min3",
            "Parādi man visas vietējās dziesmas, kurām ir vismaz trīs *** un Like",
            {
                "local_audio": "with",
                "kind_filter": "liked",
                "minimum_flag_count": 3,
                "flags": [],
            },
        ),
        _parser_case(
            "parser_wav_upload",
            "Parādi visus .wav kas ir Upload.",
            {
                "wav_scope": "all",
                "local_audio_extensions": [],
                "include_ui_types": ["Upload"],
                "exclude_ui_types": [],
            },
        ),
        _parser_case(
            "parser_local_wav_upload",
            "Parādi local .wav kam ir pazīme Upload",
            {
                "wav_scope": "local",
                "local_audio_extensions": ["wav"],
                "include_ui_types": ["Upload"],
                "exclude_ui_types": [],
            },
        ),
        _parser_case(
            "parser_wav_without_upload",
            "Parādi visus lokālos Wav - Uplod",
            {
                "wav_scope": "local",
                "local_audio_extensions": ["wav"],
                "include_ui_types": [],
                "exclude_ui_types": ["Upload"],
            },
        ),
        _parser_case(
            "parser_name",
            'Parādi dziesmas ar vārdu "Hammond" Name laukā.',
            {
                "text_query": "Hammond",
                "text_fields": ["name"],
            },
        ),
        _parser_case(
            "parser_prompt",
            'Parādi dziesmas ar vārdu "fretless" Promptā.',
            {
                "text_query": "fretless",
                "text_fields": ["prompt"],
            },
        ),
        _parser_case(
            "parser_anywhere",
            'Parādi visas vietējās dziesmas, kurām "upe" ir nosaukumā vai kur citur.',
            {
                "local_audio": "with",
                "text_query": "upe",
                "text_fields": ["name", "track_id", "lyrics", "prompt", "tags"],
            },
        ),
        _parser_case(
            "parser_locf",
            "Parādi visas dziesmas ar LocF.",
            {
                "local_family_assigned": True,
            },
        ),
    ]


def run_selection_selftest():
    """Run the built-in read-only parser + canonical DB selection regression matrix."""
    try:
        facts = _load_facts()
    except Exception as error:
        return {
            "suite": "selection",
            "suite_version": SELFTEST_SUITE_VERSION,
            "status": "UNCLEAR",
            "total": 0,
            "passed": 0,
            "failed": 0,
            "unclear": 1,
            "active_tracks": None,
            "cases": [{
                "id": "database_available",
                "status": "UNCLEAR",
                "problem": f"Kanonisko DB nevar nolasīt: {error.__class__.__name__}",
            }],
        }

    cases = []
    cases.extend(_parser_cases())
    try:
        cases.extend(_engine_cases(facts))
    except Exception as error:
        cases.append({
            "id": "engine_matrix",
            "status": "FAIL",
            "problem": f"Atlases matricas izpilde apstājās: {error.__class__.__name__}",
        })

    passed = sum(item.get("status") == "PASS" for item in cases)
    failed = sum(item.get("status") == "FAIL" for item in cases)
    unclear = sum(item.get("status") == "UNCLEAR" for item in cases)
    status = "FAIL" if failed else ("UNCLEAR" if unclear else "PASS")
    return {
        "suite": "selection",
        "suite_version": SELFTEST_SUITE_VERSION,
        "status": status,
        "total": len(cases),
        "passed": passed,
        "failed": failed,
        "unclear": unclear,
        "active_tracks": len(facts),
        "cases": cases,
    }


__all__ = ["SELFTEST_SUITE_VERSION", "run_selection_selftest"]
