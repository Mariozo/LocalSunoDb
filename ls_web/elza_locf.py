"""Read-only LocF assignment selection from authoritative LS Local Family mapping."""

import re
import urllib.parse

from ls_data.repository import get_confirmed_local_family_filter_options, search_tracks


def _clean_text(value):
    return re.sub(r"\s+", " ", str(value or "").strip())


def _mapped_track_ids():
    result = set()
    for item in get_confirmed_local_family_filter_options():
        if not isinstance(item, dict):
            continue
        for track_id in item.get("track_ids") or []:
            key = str(track_id or "").strip().casefold()
            if key:
                result.add(key)
    return result


def get_locf_selection_result(assigned, intent, limit=20):
    """Return the exact assigned/unassigned subset of the existing LS result universe."""
    if not isinstance(assigned, bool):
        raise ValueError("LocF assignment state must be boolean.")
    intent = intent if isinstance(intent, dict) else {}
    filters = dict(intent.get("filters") or {})
    try:
        preview_limit = max(1, min(int(limit), 50))
    except (TypeError, ValueError):
        preview_limit = 20

    rows = search_tracks(
        **filters,
        limit_value="all",
        sort_by="title",
        sort_dir="asc",
    )
    mapped = _mapped_track_ids()
    matches = []
    for row in rows:
        try:
            track_id = str(row["id"] or "").strip()
        except (KeyError, TypeError, IndexError):
            track_id = ""
        if not track_id:
            continue
        has_assignment = track_id.casefold() in mapped
        if has_assignment is assigned:
            matches.append(row)

    tracks = []
    for row in matches[:preview_limit]:
        tracks.append({
            "track_id": str(row["id"] or ""),
            "title": _clean_text(row["title"]),
            "workspace": _clean_text(row["workspace"]),
        })

    result = {
        "matched_count": len(matches),
        "returned_count": len(tracks),
        "tracks": tracks,
        "summary": str(intent.get("summary") or ("LocF" if assigned else "No LocF")),
        "save_name": str(intent.get("save_name") or ("LocF" if assigned else "No LocF")),
        "save_view_supported": False,
    }
    matched_ids = [str(row["id"] or "") for row in matches if row["id"]]
    if matched_ids:
        result["view_url"] = "/?" + urllib.parse.urlencode({
            "track_ids": ",".join(matched_ids),
            "rows": "300",
            "sort_by": "title",
            "sort_dir": "asc",
        })
    return result


def build_locf_selection_answer(result):
    """Render the same compact list style used by ordinary LS Elza selections."""
    result = result if isinstance(result, dict) else {}
    total = int(result.get("matched_count") or 0)
    tracks = result.get("tracks") if isinstance(result.get("tracks"), list) else []
    summary = str(result.get("summary") or "LocF")
    lines = [f"Saprastā atlase: **{summary}**.", "", f"Atrasti **{total} ieraksti**."]
    if tracks:
        lines.extend(["", f"Pirmie {len(tracks)} pēc nosaukuma:"])
        for item in tracks:
            title = str(item.get("title") or "Untitled")
            workspace = str(item.get("workspace") or "Workspace nav norādīts")
            lines.append(f"- {title} — {workspace}")
        if total > len(tracks):
            lines.extend(["", f"Čatā parādīti {len(tracks)} no {total} ierakstiem."])
    if total <= 0:
        lines.extend(["", "Darbību pogas netiek rādītas, jo atlase ir tukša."])
    return "\n".join(lines)


__all__ = ["build_locf_selection_answer", "get_locf_selection_result"]
