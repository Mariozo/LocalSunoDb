from ls_core.runtime import *

import uuid as _uuid


PLAYLISTS_PATH = DATA_DIR / "localsunodb_playlists.json"
PLAYLISTS_SCHEMA_VERSION = 1
_PLAYLIST_LOCK = threading.RLock()


def _playlist_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean_playlist_name(value):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        raise ValueError("Playlist name is required.")
    if len(text) > 120:
        raise ValueError("Playlist name is too long.")
    return text


def _clean_track_id(value):
    text = str(value or "").strip()
    if not text:
        raise ValueError("Track ID is required.")
    if len(text) > 160:
        raise ValueError("Track ID is too long.")
    return text


def _empty_playlist_store():
    return {"schema_version": PLAYLISTS_SCHEMA_VERSION, "playlists": []}


def _load_playlist_store():
    with _PLAYLIST_LOCK:
        if not PLAYLISTS_PATH.is_file():
            return _empty_playlist_store()
        try:
            payload = json.loads(PLAYLISTS_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return _empty_playlist_store()
        if not isinstance(payload, dict):
            return _empty_playlist_store()
        rows = payload.get("playlists")
        if not isinstance(rows, list):
            rows = []
        cleaned = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            playlist_id = str(item.get("id") or "").strip()
            name = str(item.get("name") or "").strip()
            if not playlist_id or not name:
                continue
            track_ids = []
            seen = set()
            for track_id in item.get("track_ids") or []:
                value = str(track_id or "").strip()
                key = value.casefold()
                if value and key not in seen:
                    seen.add(key)
                    track_ids.append(value)
            cleaned.append({
                "id": playlist_id,
                "name": name,
                "created_at": str(item.get("created_at") or ""),
                "updated_at": str(item.get("updated_at") or ""),
                "track_ids": track_ids,
            })
        return {"schema_version": PLAYLISTS_SCHEMA_VERSION, "playlists": cleaned}


def _save_playlist_store(payload):
    with _PLAYLIST_LOCK:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        normalized = {
            "schema_version": PLAYLISTS_SCHEMA_VERSION,
            "playlists": list(payload.get("playlists") or []),
        }
        temp_path = PLAYLISTS_PATH.with_suffix(PLAYLISTS_PATH.suffix + ".tmp")
        temp_path.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temp_path, PLAYLISTS_PATH)


def _playlist_by_id(payload, playlist_id):
    target = str(playlist_id or "").strip()
    for item in payload.get("playlists") or []:
        if str(item.get("id") or "") == target:
            return item
    raise ValueError("Playlist not found.")


def get_local_playlists():
    payload = _load_playlist_store()
    return [
        {
            "id": item["id"],
            "name": item["name"],
            "created_at": item.get("created_at", ""),
            "updated_at": item.get("updated_at", ""),
            "track_ids": list(item.get("track_ids") or []),
            "track_count": len(item.get("track_ids") or []),
        }
        for item in payload["playlists"]
    ]


def get_local_playlist(playlist_id):
    payload = _load_playlist_store()
    item = _playlist_by_id(payload, playlist_id)
    return {
        "id": item["id"],
        "name": item["name"],
        "created_at": item.get("created_at", ""),
        "updated_at": item.get("updated_at", ""),
        "track_ids": list(item.get("track_ids") or []),
        "track_count": len(item.get("track_ids") or []),
    }


def create_local_playlist(name):
    clean_name = _clean_playlist_name(name)
    payload = _load_playlist_store()
    now = _playlist_now()
    item = {
        "id": _uuid.uuid4().hex,
        "name": clean_name,
        "created_at": now,
        "updated_at": now,
        "track_ids": [],
    }
    payload["playlists"].append(item)
    _save_playlist_store(payload)
    return dict(item, track_count=0)


def rename_local_playlist(playlist_id, name):
    clean_name = _clean_playlist_name(name)
    payload = _load_playlist_store()
    item = _playlist_by_id(payload, playlist_id)
    item["name"] = clean_name
    item["updated_at"] = _playlist_now()
    _save_playlist_store(payload)
    return dict(item, track_count=len(item.get("track_ids") or []))


def delete_local_playlist(playlist_id):
    payload = _load_playlist_store()
    target = str(playlist_id or "").strip()
    before = len(payload["playlists"])
    payload["playlists"] = [
        item for item in payload["playlists"]
        if str(item.get("id") or "") != target
    ]
    if len(payload["playlists"]) == before:
        raise ValueError("Playlist not found.")
    _save_playlist_store(payload)
    return target


def add_tracks_to_local_playlist(playlist_id, track_ids):
    cleaned = []
    seen_input = set()
    for value in track_ids or []:
        track_id = _clean_track_id(value)
        key = track_id.casefold()
        if key in seen_input:
            continue
        seen_input.add(key)
        cleaned.append(track_id)
    if not cleaned:
        raise ValueError("At least one Track ID is required.")

    payload = _load_playlist_store()
    item = _playlist_by_id(payload, playlist_id)
    existing = {str(value).casefold() for value in item.get("track_ids") or []}
    added = []
    for track_id in cleaned:
        key = track_id.casefold()
        if key in existing:
            continue
        item.setdefault("track_ids", []).append(track_id)
        existing.add(key)
        added.append(track_id)

    if added:
        item["updated_at"] = _playlist_now()
        _save_playlist_store(payload)
    return dict(
        item,
        track_count=len(item.get("track_ids") or []),
        added_count=len(added),
        added_track_ids=added,
    )


def add_track_to_local_playlist(playlist_id, track_id):
    return add_tracks_to_local_playlist(playlist_id, [track_id])


def remove_track_from_local_playlist(playlist_id, track_id):
    track_id = _clean_track_id(track_id)
    payload = _load_playlist_store()
    item = _playlist_by_id(payload, playlist_id)
    before = list(item.get("track_ids") or [])
    item["track_ids"] = [
        value for value in before
        if str(value).casefold() != track_id.casefold()
    ]
    if item["track_ids"] != before:
        item["updated_at"] = _playlist_now()
        _save_playlist_store(payload)
    return dict(item, track_count=len(item.get("track_ids") or []))


def reorder_local_playlist(playlist_id, ordered_track_ids):
    payload = _load_playlist_store()
    item = _playlist_by_id(payload, playlist_id)
    current = list(item.get("track_ids") or [])
    current_by_key = {str(value).casefold(): str(value) for value in current}
    clean_order = []
    seen = set()
    for value in ordered_track_ids or []:
        clean = str(value or "").strip()
        key = clean.casefold()
        if clean and key in current_by_key and key not in seen:
            seen.add(key)
            clean_order.append(current_by_key[key])
    if set(seen) != set(current_by_key):
        raise ValueError("Playlist reorder must contain every current Track ID exactly once.")
    item["track_ids"] = clean_order
    item["updated_at"] = _playlist_now()
    _save_playlist_store(payload)
    return dict(item, track_count=len(clean_order))


def _playlist_track_rows(track_ids):
    ids = [str(value or "").strip() for value in track_ids if str(value or "").strip()]
    if not ids:
        return []
    try:
        rows = search_tracks(
            track_ids_filter=",".join(ids),
            limit_value="all",
        )
    except Exception:
        rows = []
    by_id = {
        str(row["id"] or "").strip().casefold(): row
        for row in rows
        if str(row["id"] or "").strip()
    }
    ordered = []
    for track_id in ids:
        row = by_id.get(track_id.casefold())
        if row is None:
            ordered.append({
                "id": track_id,
                "title": "[Track nav pašreizējā DB]",
                "workspace": "",
                "duration": "",
                "missing": True,
            })
        else:
            item = dict(row)
            item["missing"] = False
            ordered.append(item)
    return ordered


def _playlist_cover_html(track_ids, css_class="playlist-cover"):
    ids = [str(value or "").strip() for value in track_ids[:4] if str(value or "").strip()]
    if not ids:
        return f'<div class="{css_class} playlist-cover-empty">♪</div>'
    images = "".join(
        f'<img src="/suno-image?track_id={urllib.parse.quote(track_id)}" alt="">'
        for track_id in ids
    )
    return f'<div class="{css_class} playlist-cover-grid cover-count-{len(ids)}">{images}</div>'


def _playlist_catalog_html(playlists, add_track_id=""):
    pending_track_id = str(add_track_id or "").strip()
    cards = [
        """
        <button type="button" class="playlist-card playlist-new-card" id="playlist-new-card">
            <span class="playlist-new-plus">＋</span>
            <strong>New Playlist</strong>
        </button>
        """
    ]
    for item in playlists:
        playlist_id = esc(item["id"])
        name = esc(item["name"])
        count = int(item["track_count"])
        cover = _playlist_cover_html(item["track_ids"], "playlist-card-cover")
        if pending_track_id:
            cards.append(f"""
                <form class="playlist-card playlist-add-target" method="post" action="/playlist-add-track-open">
                    <input type="hidden" name="playlist_id" value="{playlist_id}">
                    <input type="hidden" name="track_id" value="{esc(pending_track_id)}">
                    <button type="submit" class="playlist-card-submit" title="Add song to {name}">
                        {cover}
                        <strong>{name}</strong>
                        <span>{count} {'song' if count == 1 else 'songs'} now · +1 selected</span>
                    </button>
                </form>
            """)
        else:
            cards.append(f"""
                <a class="playlist-card" href="/playlists?id={playlist_id}">
                    {cover}
                    <strong>{name}</strong>
                    <span>{count} {'song' if count == 1 else 'songs'}</span>
                </a>
            """)
    return "".join(cards)


def _playlist_detail_rows(playlist):
    rows = _playlist_track_rows(playlist["track_ids"])
    html_rows = []
    for index, row in enumerate(rows, start=1):
        track_id = str(row.get("id") or "")
        title = str(row.get("title") or "[No title]")
        workspace = str(row.get("workspace") or "")
        duration = format_duration(row.get("duration") or "")
        missing = bool(row.get("missing"))
        play_disabled = " disabled" if missing else ""
        missing_badge = '<span class="playlist-missing-badge">Missing</span>' if missing else ""
        html_rows.append(f"""
            <div class="playlist-track-row{' is-missing' if missing else ''}"
                 draggable="true" data-track-id="{esc(track_id)}">
                <button class="playlist-drag-handle" type="button" title="Velc, lai mainītu secību" aria-label="Velc, lai mainītu secību">⋮⋮</button>
                <span class="playlist-track-number">{index}</span>
                <img class="playlist-track-cover" src="/suno-image?track_id={urllib.parse.quote(track_id)}" alt="">
                <button type="button" class="playlist-track-play" data-track-id="{esc(track_id)}"{play_disabled}>▶</button>
                <div class="playlist-track-copy">
                    <strong>{esc(title)}</strong>
                    <span>{esc(workspace)} {missing_badge}</span>
                </div>
                <span class="playlist-track-duration">{esc(duration)}</span>
                <button type="button" class="playlist-track-remove" data-track-id="{esc(track_id)}" title="Remove from Playlist">−</button>
            </div>
        """)
    if not html_rows:
        return '<div class="playlist-empty-state">Playlist ir tukša. Spied Add songs, tad Suno Library izmanto Select WAV un izvēlies lokālos ierakstus.</div>'
    return "".join(html_rows)


def _playlist_page_style():
    return """
    :root{color-scheme:dark;font-family:Inter,Segoe UI,Arial,sans-serif}
    *{box-sizing:border-box}body{margin:0;background:#0e0e10;color:#f5f5f5}
    a{color:inherit;text-decoration:none}button,input{font:inherit}
    .playlist-shell{min-height:100vh;padding-bottom:84px}
    .playlist-topbar{height:64px;border-bottom:1px solid #262629;display:flex;align-items:center;padding:0 28px;gap:24px;position:sticky;top:0;background:#0e0e10;z-index:5}
    .playlist-brand{font-size:23px;font-weight:800;letter-spacing:.04em}.playlist-nav{display:flex;gap:8px}
    .playlist-nav a{padding:10px 14px;border-radius:20px;color:#b8b8bd}.playlist-nav a.active,.playlist-nav a:hover{background:#252528;color:#fff}
    .playlist-main{padding:28px 44px;max-width:1500px;margin:0 auto}.playlist-search{width:100%;background:#1a1a1d;border:1px solid #242428;color:#fff;border-radius:12px;padding:14px 16px;margin-bottom:28px}
    .playlist-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:24px}
    .playlist-card{display:flex;flex-direction:column;gap:9px;min-width:0;text-align:left;background:transparent;border:0;color:#fff;cursor:pointer}
    .playlist-card strong{font-size:17px}.playlist-card span{color:#a8a8ad}.playlist-new-card{height:245px;border:1px solid #4a4a50;border-radius:16px;background:#242429;align-items:center;justify-content:center}
    .playlist-add-target{margin:0}.playlist-card-submit{display:flex;flex-direction:column;gap:9px;width:100%;padding:0;border:0;background:transparent;color:#fff;text-align:left;cursor:pointer}.playlist-card-submit strong{font-size:17px}.playlist-card-submit span{color:#a8a8ad}
    .playlist-new-plus{font-size:44px!important;color:#fff!important}.playlist-card-cover,.playlist-cover{height:200px;border-radius:16px;overflow:hidden;background:#222;display:grid}
    .playlist-cover-grid img{width:100%;height:100%;object-fit:cover;min-width:0;min-height:0}.cover-count-2,.cover-count-3,.cover-count-4{grid-template-columns:1fr 1fr}.cover-count-3,.cover-count-4{grid-template-rows:1fr 1fr}.cover-count-3 img:first-child{grid-row:1/3}
    .playlist-cover-empty{display:flex;align-items:center;justify-content:center;font-size:60px;color:#777}
    .playlist-hero{display:flex;gap:28px;align-items:flex-end;margin-bottom:24px}.playlist-hero .playlist-cover{width:220px;height:220px;flex:0 0 220px}
    .playlist-hero-copy h1{font-size:42px;margin:0 0 10px}.playlist-hero-copy p{color:#aaa;margin:0 0 22px}
    .playlist-actions{display:flex;gap:10px;flex-wrap:wrap}.playlist-primary,.playlist-secondary{border:0;border-radius:24px;padding:12px 20px;cursor:pointer}
    .playlist-primary{background:#f5f2ed;color:#101012}.playlist-secondary{background:#2b2b30;color:#fff}.playlist-danger{color:#ff6f64}
    .playlist-detail-search{margin:12px 0 18px}.playlist-tracks{display:flex;flex-direction:column}
    .playlist-track-row{display:grid;grid-template-columns:34px 42px 58px 36px minmax(0,1fr) 72px 44px;gap:12px;align-items:center;padding:10px 8px;border-radius:10px}
    .playlist-track-row:hover{background:#18181b}.playlist-track-row.dragging{opacity:.45}.playlist-track-row.drag-over{outline:1px solid #73737b}
    .playlist-drag-handle,.playlist-track-play,.playlist-track-remove{border:0;background:transparent;color:#c8c8cd;cursor:pointer}
    .playlist-drag-handle{cursor:grab}.playlist-track-number{color:#8e8e95;text-align:right}.playlist-track-cover{width:54px;height:54px;border-radius:8px;object-fit:cover;background:#222}
    .playlist-track-copy{display:flex;flex-direction:column;gap:5px;min-width:0}.playlist-track-copy strong{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.playlist-track-copy span{font-size:13px;color:#929299}
    .playlist-track-duration{color:#aaa;text-align:right}.playlist-track-remove{font-size:24px}.playlist-missing-badge{color:#e58c83!important;margin-left:8px}
    .playlist-empty-state{padding:50px;text-align:center;color:#999;border:1px dashed #35353a;border-radius:14px}
    .playlist-player{position:fixed;left:0;right:0;bottom:0;height:74px;background:#09090a;border-top:1px solid #262629;display:grid;grid-template-columns:minmax(220px,1fr) minmax(360px,700px) minmax(220px,1fr);align-items:center;padding:0 28px;z-index:8}
    .playlist-player-title{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.playlist-player-controls{display:flex;align-items:center;justify-content:center;gap:12px}.playlist-player-controls button{border:0;background:transparent;color:#fff;font-size:22px;cursor:pointer}
    .playlist-player audio{width:100%;height:36px}.playlist-player-spacer{min-width:0}
    @media(max-width:800px){.playlist-main{padding:20px}.playlist-hero{align-items:flex-start}.playlist-hero .playlist-cover{width:150px;height:150px;flex-basis:150px}.playlist-track-row{grid-template-columns:28px 34px 48px 32px minmax(0,1fr) 40px}.playlist-track-duration{display:none}.playlist-player{grid-template-columns:1fr;padding:8px 14px;height:92px}.playlist-player-title{display:none}}
    """


def _playlist_page_script(active_playlist_id="", pending_track_id=""):
    active_json = json.dumps(str(active_playlist_id or ""))
    pending_json = json.dumps(str(pending_track_id or ""))
    return f"""
    (() => {{
      const activePlaylistId = {active_json};
      const pendingTrackId = {pending_json};
      const post = async (path, values={{}}) => {{
        const body = new URLSearchParams();
        Object.entries(values).forEach(([key, value]) => body.set(key, String(value ?? "")));
        const response = await fetch(path, {{method:"POST",headers:{{"Content-Type":"application/x-www-form-urlencoded"}},body:body.toString()}});
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || "Playlist operation failed.");
        return data;
      }};

      const newCard = document.getElementById("playlist-new-card");
      if (newCard) newCard.addEventListener("click", async () => {{
        const name = window.prompt("Playlist name");
        if (!name) return;
        try {{
          const data = await post("/playlist-create", {{name}});
          if (pendingTrackId) {{
            await post("/playlist-add-track", {{
              playlist_id: data.playlist.id,
              track_id: pendingTrackId,
            }});
          }}
          window.location.href = "/playlists?id=" + encodeURIComponent(data.playlist.id);
        }} catch (error) {{ window.alert(error.message); }}
      }});

      const search = document.getElementById("playlist-search");
      if (search) search.addEventListener("input", () => {{
        const needle = search.value.trim().toLocaleLowerCase();
        document.querySelectorAll(".playlist-card[href], .playlist-add-target").forEach((card) => {{
          card.hidden = needle && !card.textContent.toLocaleLowerCase().includes(needle);
        }});
      }});

      if (!activePlaylistId) return;

      const rename = document.getElementById("playlist-rename");
      if (rename) rename.addEventListener("click", async () => {{
        const current = document.getElementById("playlist-title")?.textContent || "";
        const name = window.prompt("Playlist name", current);
        if (!name || name === current) return;
        try {{
          await post("/playlist-rename", {{playlist_id: activePlaylistId, name}});
          window.location.reload();
        }} catch (error) {{ window.alert(error.message); }}
      }});

      const removePlaylist = document.getElementById("playlist-delete");
      if (removePlaylist) removePlaylist.addEventListener("click", async () => {{
        if (!window.confirm("Delete this playlist? Songs will not be deleted.")) return;
        try {{
          await post("/playlist-delete", {{playlist_id: activePlaylistId}});
          window.location.href = "/playlists";
        }} catch (error) {{ window.alert(error.message); }}
      }});

      const rowsBox = document.getElementById("playlist-tracks");
      const renumber = () => {{
        if (!rowsBox) return;
        rowsBox.querySelectorAll(".playlist-track-row").forEach((row, index) => {{
          const cell = row.querySelector(".playlist-track-number");
          if (cell) cell.textContent = String(index + 1);
        }});
      }};
      const saveOrder = async () => {{
        if (!rowsBox) return;
        const ids = Array.from(rowsBox.querySelectorAll(".playlist-track-row")).map((row) => row.dataset.trackId);
        await post("/playlist-reorder", {{playlist_id: activePlaylistId, track_ids: ids.join(",")}});
      }};

      let dragged = null;
      if (rowsBox) {{
        rowsBox.addEventListener("dragstart", (event) => {{
          const row = event.target.closest(".playlist-track-row");
          if (!row) return;
          dragged = row;
          row.classList.add("dragging");
          if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
        }});
        rowsBox.addEventListener("dragend", async () => {{
          if (dragged) dragged.classList.remove("dragging");
          rowsBox.querySelectorAll(".drag-over").forEach((row) => row.classList.remove("drag-over"));
          dragged = null;
          renumber();
          try {{ await saveOrder(); }} catch (error) {{ window.alert(error.message); window.location.reload(); }}
        }});
        rowsBox.addEventListener("dragover", (event) => {{
          event.preventDefault();
          const target = event.target.closest(".playlist-track-row");
          if (!dragged || !target || dragged === target) return;
          rowsBox.querySelectorAll(".drag-over").forEach((row) => row.classList.remove("drag-over"));
          target.classList.add("drag-over");
          const rect = target.getBoundingClientRect();
          const after = event.clientY > rect.top + rect.height / 2;
          rowsBox.insertBefore(dragged, after ? target.nextSibling : target);
        }});
        rowsBox.addEventListener("drop", (event) => {{
          event.preventDefault();
          rowsBox.querySelectorAll(".drag-over").forEach((row) => row.classList.remove("drag-over"));
        }});

        rowsBox.addEventListener("click", async (event) => {{
          const remove = event.target.closest(".playlist-track-remove");
          if (remove) {{
            try {{
              await post("/playlist-remove-track", {{playlist_id: activePlaylistId, track_id: remove.dataset.trackId}});
              remove.closest(".playlist-track-row")?.remove();
              renumber();
            }} catch (error) {{ window.alert(error.message); }}
            return;
          }}
          const play = event.target.closest(".playlist-track-play");
          if (play) playTrack(play.dataset.trackId, true);
        }});
      }}

      const detailSearch = document.getElementById("playlist-detail-search");
      if (detailSearch) detailSearch.addEventListener("input", () => {{
        const needle = detailSearch.value.trim().toLocaleLowerCase();
        rowsBox?.querySelectorAll(".playlist-track-row").forEach((row) => {{
          row.hidden = needle && !row.textContent.toLocaleLowerCase().includes(needle);
        }});
      }});

      const audio = document.getElementById("playlist-audio");
      const nowTitle = document.getElementById("playlist-player-title");
      let currentIndex = -1;
      const orderedRows = () => Array.from(rowsBox?.querySelectorAll(".playlist-track-row:not(.is-missing)") || []);
      const playTrack = (trackId, autoplay=true) => {{
        const rows = orderedRows();
        const index = rows.findIndex((row) => row.dataset.trackId === trackId);
        if (index < 0 || !audio) return;
        currentIndex = index;
        const row = rows[index];
        const title = row.querySelector(".playlist-track-copy strong")?.textContent || trackId;
        if (nowTitle) nowTitle.textContent = title;
        audio.src = "/playback-media?track_id=" + encodeURIComponent(trackId) + "&source=suno";
        if (autoplay) audio.play().catch(() => {{}});
      }};
      const playAt = (index) => {{
        const rows = orderedRows();
        if (!rows.length) return;
        const normalized = (index + rows.length) % rows.length;
        playTrack(rows[normalized].dataset.trackId, true);
      }};

      document.getElementById("playlist-play-all")?.addEventListener("click", () => playAt(0));
      document.getElementById("playlist-player-prev")?.addEventListener("click", () => playAt(currentIndex <= 0 ? 0 : currentIndex - 1));
      document.getElementById("playlist-player-next")?.addEventListener("click", () => playAt(currentIndex + 1));
      audio?.addEventListener("ended", () => {{
        const rows = orderedRows();
        if (currentIndex >= 0 && currentIndex + 1 < rows.length) playAt(currentIndex + 1);
      }});
    }})();
    """


def render_playlists_page(playlist_id="", add_track_id=""):
    playlists = get_local_playlists()
    pending_track_id = str(add_track_id or "").strip()
    active = None
    if playlist_id:
        try:
            active = get_local_playlist(playlist_id)
        except ValueError:
            active = None

    if active is None:
        chooser_title = (
            '<h1 style="margin:0 0 18px;font-size:30px">Choose Playlist</h1>'
            '<p style="margin:-8px 0 22px;color:#aaa">Add the selected song to one local playlist.</p>'
            if pending_track_id else ""
        )
        main = f"""
          <main class="playlist-main">
            {chooser_title}
            <input id="playlist-search" class="playlist-search" type="search" placeholder="Search for a playlist">
            <div class="playlist-grid">{_playlist_catalog_html(playlists, pending_track_id)}</div>
          </main>
        """
        active_id = ""
    else:
        cover = _playlist_cover_html(active["track_ids"], "playlist-cover")
        main = f"""
          <main class="playlist-main">
            <section class="playlist-hero">
              {cover}
              <div class="playlist-hero-copy">
                <h1 id="playlist-title">{esc(active["name"])}</h1>
                <p>{int(active["track_count"])} songs · manual order</p>
                <div class="playlist-actions">
                  <button type="button" class="playlist-primary" id="playlist-play-all">▶ Play</button>
                  <button type="button" class="playlist-secondary" id="playlist-rename">Edit playlist details</button>
                  <a class="playlist-secondary" href="/?{urllib.parse.urlencode({'playlist_add': active['id'], 'local_audio_filter': 'with'})}">＋ Add songs</a>
                  <button type="button" class="playlist-secondary playlist-danger" id="playlist-delete">Delete playlist</button>
                </div>
              </div>
            </section>
            <input id="playlist-detail-search" class="playlist-search playlist-detail-search" type="search" placeholder="Search in this playlist">
            <section class="playlist-tracks" id="playlist-tracks">{_playlist_detail_rows(active)}</section>
          </main>
          <footer class="playlist-player">
            <div class="playlist-player-title" id="playlist-player-title">Playlist</div>
            <div class="playlist-player-controls">
              <button type="button" id="playlist-player-prev" title="Previous">⏮</button>
              <audio id="playlist-audio" controls preload="metadata"></audio>
              <button type="button" id="playlist-player-next" title="Next">⏭</button>
            </div>
            <div class="playlist-player-spacer"></div>
          </footer>
        """
        active_id = active["id"]

    html_text = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Playlists · LocalSunoDb</title>
<link rel="icon" type="image/x-icon" href="/ls-static/ls_web/static/LS.ico?v={esc(APP_VERSION)}">
<style>{_playlist_page_style()}</style>
</head>
<body>
<div class="playlist-shell">
<header class="playlist-topbar">
  <a class="playlist-brand" href="/">LS</a>
  <nav class="playlist-nav">
    <a href="/">Suno Library</a>
    <a class="active" href="/playlists">Playlists</a>
  </nav>
</header>
{main}
</div>
<script>{_playlist_page_script(active_id, pending_track_id if active is None else "")}</script>
</body>
</html>"""
    return html_text.encode("utf-8")


def render_playlist_library_actions_script():
    return r"""
<script>
(() => {
  if (window.LSPlaylistLibraryActionsInstalled) return;
  window.LSPlaylistLibraryActionsInstalled = true;

  const post = async (path, values={}) => {
    const body = new URLSearchParams();
    Object.entries(values).forEach(([key, value]) => body.set(key, String(value ?? "")));
    const response = await fetch(path, {method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body:body.toString()});
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || "Playlist operation failed.");
    return data;
  };

  const cleanTrackIds = (values) => {
    const seen = new Set();
    return (Array.isArray(values) ? values : [values])
      .map((value) => String(value || "").trim())
      .filter((value) => {
        const key = value.toLowerCase();
        if (!value || seen.has(key)) return false;
        seen.add(key);
        return true;
      });
  };

  const addTracks = async (playlistId, trackIds) => {
    const ids = cleanTrackIds(trackIds);
    if (!ids.length) throw new Error("No tracks selected.");
    return await post("/playlist-add-tracks", {
      playlist_id: playlistId,
      track_ids: ids.join(","),
    });
  };

  const fetchPlaylists = async () => {
    const response = await fetch("/playlists-json", {cache:"no-store"});
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || "Could not load playlists.");
    return Array.isArray(data.playlists) ? data.playlists : [];
  };

  const choosePlaylist = async (trackIds) => {
    const ids = cleanTrackIds(trackIds);
    if (!ids.length) return null;

    const playlists = await fetchPlaylists();
    let playlist = null;
    if (!playlists.length) {
      const name = window.prompt("No playlists yet. New playlist name:");
      if (!name) return null;
      const created = await post("/playlist-create", {name});
      playlist = created.playlist;
    } else {
      const lines = playlists
        .map((item, index) => String(index + 1) + ". " + item.name + " (" + item.track_count + ")")
        .join("\n");
      const answer = window.prompt(
        "Add " + ids.length + (ids.length === 1 ? " song" : " songs") +
        " to Playlist — enter number:\n\n0. + New Playlist\n" + lines,
        "1"
      );
      if (answer === null || String(answer).trim() === "") return null;
      const number = Number.parseInt(answer, 10);
      if (number === 0) {
        const name = window.prompt("New playlist name:");
        if (!name) return null;
        const created = await post("/playlist-create", {name});
        playlist = created.playlist;
      } else {
        const index = number - 1;
        if (!Number.isInteger(index) || index < 0 || index >= playlists.length) {
          throw new Error("Invalid playlist number.");
        }
        playlist = playlists[index];
      }
    }

    const result = await addTracks(playlist.id, ids);
    const added = Number(result.playlist?.added_count || 0);
    const skipped = ids.length - added;
    const suffix = skipped > 0 ? " · " + skipped + " already there" : "";
    window.alert("Playlist: " + playlist.name + "\nAdded: " + added + suffix);
    return result;
  };

  const getSelectedTrackIds = () => {
    const wavIds = window.LS?.library?.getSelectedLocalWavTrackIds?.();
    if (Array.isArray(wavIds)) return cleanTrackIds(wavIds);
    return Array.from(
      document.querySelectorAll("#tracks-table tbody .track-check:checked")
    ).map((check) => String(check.value || "").trim()).filter(Boolean);
  };

  const selectedButton = document.getElementById("add-selected-playlist-btn");
  const table = document.getElementById("tracks-table");
  const params = new URLSearchParams(window.location.search);
  const playlistAddId = String(params.get("playlist_add") || "").trim();
  let playlistAddName = "";

  const syncSelectedButton = () => {
    if (!selectedButton) return;
    const count = getSelectedTrackIds().length;
    selectedButton.disabled = count < 1;
    if (playlistAddId) {
      selectedButton.style.display = count > 0 ? "" : "none";
      selectedButton.textContent = count > 0
        ? "Add to " + (playlistAddName || "Playlist") + " (" + count + ")"
        : "Add to " + (playlistAddName || "Playlist");
      selectedButton.title = playlistAddName
        ? "Add " + count + " selected local WAV " + (count === 1 ? "track" : "tracks") + " to " + playlistAddName
        : "Add selected local WAV tracks to this playlist";
      return;
    }
    selectedButton.style.display = count > 0 ? "" : "none";
    selectedButton.textContent = count > 0 ? "Add to Playlist (" + count + ")" : "Add to Playlist";
  };

  const enterPlaylistAddMode = async () => {
    if (!playlistAddId || !table) return;
    const playlists = await fetchPlaylists();
    const playlist = playlists.find((item) => String(item.id || "") === playlistAddId);
    if (!playlist) throw new Error("Playlist not found.");
    playlistAddName = String(playlist.name || "Playlist");

    table.querySelectorAll("tbody .track-check:checked").forEach((check) => {
      check.checked = false;
    });
    table.classList.remove("selection-mode");

    const wavButton = document.getElementById("wav-select-mode-btn");
    if (wavButton) {
      wavButton.style.display = "";
      wavButton.textContent = "Select WAV";
      wavButton.title = "Select local WAV tracks to add to " + playlistAddName;
    }

    const panel = document.querySelector("main > .panel");
    if (panel && !document.getElementById("playlist-add-mode-banner")) {
      const banner = document.createElement("div");
      banner.id = "playlist-add-mode-banner";
      banner.style.cssText = "display:flex;align-items:center;gap:12px;margin:0 0 12px;padding:10px 14px;border:1px solid rgba(255,255,255,.16);border-radius:12px;background:rgba(255,255,255,.06);color:#fff;";
      const text = document.createElement("strong");
      text.textContent = "Add to " + playlistAddName + " · Local only · press Select WAV";
      const back = document.createElement("a");
      back.href = "/playlists?id=" + encodeURIComponent(playlistAddId);
      back.textContent = "Back to playlist";
      back.style.cssText = "margin-left:auto;color:inherit;text-decoration:underline;";
      banner.appendChild(text);
      banner.appendChild(back);
      panel.appendChild(banner);
    }
    syncSelectedButton();
  };

  document.addEventListener("change", (event) => {
    if (event.target?.matches?.("#tracks-table .track-check")) syncSelectedButton();
  });
  document.addEventListener("ls-library-wav-selection-changed", syncSelectedButton);

  if (selectedButton) {
    selectedButton.addEventListener("click", async () => {
      const ids = getSelectedTrackIds();
      if (!ids.length) return;
      selectedButton.disabled = true;
      try {
        if (playlistAddId) {
          const result = await addTracks(playlistAddId, ids);
          const added = Number(result.playlist?.added_count || 0);
          window.location.href = "/playlists?id=" + encodeURIComponent(playlistAddId) + "&added=" + encodeURIComponent(String(added));
          return;
        }
        await choosePlaylist(ids);
      } catch (error) {
        window.alert(error.message);
      } finally {
        syncSelectedButton();
      }
    });
  }

  // Playlist additions use the shared Select WAV multi-selection flow.

  enterPlaylistAddMode().catch((error) => {
    window.alert(error.message);
  });
  window.setTimeout(syncSelectedButton, 0);
})();
</script>
"""


def playlists_json_payload():
    return {"ok": True, "playlists": get_local_playlists()}
