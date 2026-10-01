from __future__ import annotations

import html
import json
import urllib.parse

from ls_core.runtime import APP_VERSION
from ls_data.music_library import list_music_databases, music_database_albums, music_database_tracks
from ls_library.playlists import get_local_playlists


def _esc(value):
    return html.escape(str(value or ""), quote=True)


def _url(**params):
    clean = {key: value for key, value in params.items() if str(value or "").strip() != ""}
    return "/my-library" + ("?" + urllib.parse.urlencode(clean) if clean else "")


def _duration(value):
    try:
        seconds = int(round(float(value or 0)))
    except Exception:
        return ""
    if seconds <= 0:
        return ""
    return f"{seconds // 60}:{seconds % 60:02d}"


def _duration_summary(value):
    try:
        seconds = int(round(float(value or 0)))
    except Exception:
        return ""
    if seconds <= 0:
        return ""
    if seconds < 60:
        return f"{seconds} s"
    minutes, remain = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes} min" + (f" {remain} s" if remain else "")
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h" + (f" {minutes} min" if minutes else "")


def _sidebar():
    return """
    <aside class="side">
      <div class="side-brand">LS <span>v%s</span></div>
      <nav>
        <a href="/" class="nav-item">
          <span class="nav-icon">☁</span><span>Suno Library</span>
        </a>
        <a href="/my-library" class="nav-item active">
          <span class="nav-icon">◫</span><span>My Library</span>
        </a>
        <a href="/playlists" class="nav-item">
          <span class="nav-icon">☷</span><span>Playlists</span>
        </a>
        <a href="/downloader" class="nav-item">
          <span class="nav-icon">⇩</span><span>Imports</span>
        </a>
      </nav>
    </aside>
    """ % _esc(APP_VERSION)


def render_music_database_page(name="", query="", view="grid", album="", artist="", year="", open_new=False):
    catalog = list_music_databases().get("databases") or []
    usable = [item for item in catalog if not item.get("error")]
    requested = str(name or "").strip()
    selected = next((item for item in usable if str(item.get("name") or "") == requested), None)
    if selected is None and usable:
        selected = usable[0]
    selected_name = str((selected or {}).get("name") or "")
    query = str(query or "").strip()
    view = "list" if str(view or "").strip().lower() == "list" else "grid"
    album = str(album or "").strip()
    artist = str(artist or "").strip()
    year = str(year or "").strip()

    albums = []
    tracks = []
    root_folder = ""
    total_tracks = 0
    if selected_name:
        data = music_database_albums(selected_name, query=query)
        albums = data.get("albums") or []
        root_folder = str(data.get("root_folder") or "")
        total_tracks = int(data.get("total_tracks") or 0)
        if view == "list" or album:
            tracks = (music_database_tracks(
                selected_name,
                query=query if not album else "",
                album=album,
                artist=artist,
                year=year,
            ).get("rows") or [])

    db_options = ['<option value="">— nav DB —</option>']
    for item in usable:
        db_name = str(item.get("name") or "")
        chosen = " selected" if db_name == selected_name else ""
        db_options.append(
            f'<option value="{_esc(db_name)}"{chosen}>{_esc(db_name)} · {int(item.get("track_count") or 0)} dziesmas</option>'
        )

    cards = []
    for item in albums:
        a_artist = str(item.get("artist") or "Unknown Artist")
        a_album = str(item.get("album") or "Singles")
        a_year = str(item.get("year") or "")
        cover_sha = str(item.get("cover_sha1") or "")
        cover = (
            f'<img src="/music-db-cover?name={urllib.parse.quote(selected_name)}&sha1={urllib.parse.quote(cover_sha)}" alt="">'
            if cover_sha else '<div class="cover-empty">♪</div>'
        )
        detail_url = _url(db=selected_name, album=a_album, artist=a_artist, year=a_year)
        title_line = " · ".join(part for part in [a_artist, a_year] if part)
        cards.append(f"""
        <a class="album-card" href="{_esc(detail_url)}">
          <div class="album-cover">{cover}</div>
          <div class="album-meta">
            <div class="album-artist">{_esc(title_line)}</div>
            <div class="album-title">{_esc(a_album)}</div>
            <div class="album-count">{int(item.get('track_count') or 0)} songs</div>
          </div>
        </a>""")

    row_html = []
    album_row_html = []
    album_artist_key = artist.casefold()
    for index, row in enumerate(tracks):
        track_no = row.get("track_no")
        disc_no = row.get("disc_no")
        num = ""
        if disc_no and int(disc_no) > 1:
            num += f"{int(disc_no)}."
        if track_no:
            num += str(int(track_no))
        play_artist = str(row.get("artist") or row.get("album_artist") or "")
        play_album = str(row.get("album") or "")
        play_title = str(row.get("title") or row.get("filename") or "Track")
        play_path = str(row.get("path") or "")
        cover_sha = str(row.get("cover_sha1") or "")
        play_cover = (
            f"/music-db-cover?name={urllib.parse.quote(selected_name)}&sha1={urllib.parse.quote(cover_sha)}"
            if cover_sha and selected_name else ""
        )
        row_html.append(f"""
          <tr class="music-track-row"
              data-player-index="{index}"
              data-player-path="{_esc(play_path)}"
              data-player-title="{_esc(play_title)}"
              data-player-artist="{_esc(play_artist)}"
              data-player-album="{_esc(play_album)}"
              data-player-cover="{_esc(play_cover)}"
              data-track-year="{_esc(row.get('year'))}"
              data-track-genre="{_esc(row.get('genre'))}"
              data-track-format="{_esc(str(row.get('format') or '').upper())}"
              data-track-duration="{_esc(_duration(row.get('duration_seconds')))}">
            <td class="track-number-cell"><button type="button" class="music-row-play" aria-label="Atskaņot {_esc(play_title)}" title="Atskaņot">▶</button><span>{_esc(num)}</span></td>
            <td><strong>{_esc(play_title)}</strong><div class="path-line">{_esc(play_path)}</div></td>
            <td>{_esc(play_artist)}</td>
            <td>{_esc(play_album)}</td>
            <td>{_esc(row.get('year'))}</td>
            <td>{_esc(row.get('genre'))}</td>
            <td>{_esc(str(row.get('format') or '').upper())}</td>
            <td>{_esc(_duration(row.get('duration_seconds')))}</td>
          </tr>""")

        detail_artist = ""
        if play_artist and play_artist.casefold() != album_artist_key:
            detail_artist = f'<span>{_esc(play_artist)}</span>'
        cover_cell = (
            f'<img src="{_esc(play_cover)}" alt="">'
            if play_cover else '<span class="album-track-cover-empty">♪</span>'
        )
        album_row_html.append(f"""
          <div class="album-track-row music-track-row"
              data-player-index="{index}"
              data-player-path="{_esc(play_path)}"
              data-player-title="{_esc(play_title)}"
              data-player-artist="{_esc(play_artist)}"
              data-player-album="{_esc(play_album)}"
              data-player-cover="{_esc(play_cover)}"
              data-track-year="{_esc(row.get('year'))}"
              data-track-genre="{_esc(row.get('genre'))}"
              data-track-format="{_esc(str(row.get('format') or '').upper())}"
              data-track-duration="{_esc(_duration(row.get('duration_seconds')))}">
            <span class="album-track-number">{_esc(num or index + 1)}</span>
            <button type="button" class="music-row-play album-row-play" aria-label="Atskaņot {_esc(play_title)}" title="Atskaņot">▶</button>
            <span class="album-track-cover">{cover_cell}</span>
            <span class="album-track-copy"><strong>{_esc(play_title)}</strong>{detail_artist}</span>
            <span class="album-track-duration">{_esc(_duration(row.get('duration_seconds')))}</span>
          </div>""")

    if album:
        heading = album
        back_url = _url(db=selected_name, q=query)
    else:
        heading = selected_name or "My Library"
        back_url = ""

    album_total_seconds = sum(
        float(row.get("duration_seconds") or 0)
        for row in tracks
        if row.get("duration_seconds")
    )
    album_total_duration = _duration_summary(album_total_seconds)
    album_cover_sha = next(
        (str(row.get("cover_sha1") or "") for row in tracks if row.get("cover_sha1")),
        "",
    )
    album_cover_url = (
        f"/music-db-cover?name={urllib.parse.quote(selected_name)}&sha1={urllib.parse.quote(album_cover_sha)}"
        if album_cover_sha and selected_name else ""
    )
    album_meta = " · ".join(part for part in [
        year,
        f"{len(tracks)} dziesmas",
        album_total_duration,
    ] if part)

    empty = ""
    if not usable:
        empty = """
        <section class="empty-state">
          <div class="empty-icon">♫</div>
          <h2>My Library vēl nav nevienas atsevišķas DB</h2>
          <p>Šeit Suno dati netiek izmantoti. Izveido atsevišķu mūzikas DB savai MP3 kolekcijai.</p>
          <button class="primary" id="empty-new-db">Izveidot pirmo DB</button>
        </section>"""
    elif not albums and not album:
        empty = '<section class="empty-state"><h2>Nekas nav atrasts</h2><p>Maini meklēšanas tekstu vai izvēlies citu DB.</p></section>'

    detail_block = ""
    if album:
        hero_cover = (
            f'<img id="album-hero-cover" src="{_esc(album_cover_url)}" alt="">'
            if album_cover_url else '<span class="album-hero-cover-empty">♪</span>'
        )
        detail_block = f"""
        <section class="album-detail-v2">
          <div class="album-hero-v2" id="album-hero-v2">
            <a class="album-back-v2" href="{_esc(back_url)}" title="Atpakaļ uz albumiem">←</a>
            <div class="album-hero-inner-v2">
              <div class="album-hero-cover-v2">{hero_cover}</div>
              <div class="album-hero-copy-v2">
                <div class="album-kind-v2">Albums</div>
                <h1>{_esc(album)}</h1>
                <div class="album-meta-v2"><strong>{_esc(artist or "Unknown Artist")}</strong>{(" · " + _esc(album_meta)) if album_meta else ""}</div>
              </div>
            </div>
          </div>
          <div class="album-actions-v2">
            <button type="button" class="album-play-v2" id="album-play-all" title="Atskaņot albumu" aria-label="Atskaņot albumu">▶</button>
            <input type="search" class="album-search-v2" id="album-track-search" placeholder="Meklēt šajā albumā" autocomplete="off">
          </div>
          <div class="album-track-head-v2"><span>#</span><span>Nosaukums</span><span>◷</span></div>
          <div class="album-track-list-v2" id="album-track-list">
            {''.join(album_row_html) if album_row_html else '<div class="none">Nav ierakstu.</div>'}
          </div>
        </section>"""

    list_block = ""
    if not album:
        list_block = f"""
        <div class="view-panel list-panel{' visible' if view == 'list' else ''}">
          <div class="track-table-wrap"><table class="track-table">
            <thead><tr><th>#</th><th>Nosaukums</th><th>Autors</th><th>Albums</th><th>Gads</th><th>Žanrs</th><th>Tips</th><th>Ilgums</th></tr></thead>
            <tbody>{''.join(row_html) if row_html else '<tr><td colspan="8" class="none">Nav ierakstu.</td></tr>'}</tbody>
          </table></div>
        </div>"""

    grid_block = ""
    if not album:
        grid_block = f'<div class="view-panel grid-panel{" visible" if view == "grid" else ""}"><div class="album-grid">{"".join(cards)}</div>{empty}</div>'

    playlists = get_local_playlists()
    playlist_rows = []
    for item in playlists:
        playlist_id = str(item.get("id") or "")
        playlist_name = str(item.get("name") or "Playlist")
        count = int(item.get("track_count") or 0)
        playlist_rows.append(f"""
        <a class="home-playlist-row" href="/playlists?id={urllib.parse.quote(playlist_id)}">
          <div class="home-playlist-icon">☷</div>
          <div class="home-playlist-copy"><strong>{_esc(playlist_name)}</strong><span>{count} {'song' if count == 1 else 'songs'}</span></div>
          <div class="home-playlist-arrow">›</div>
        </a>""")
    playlists_block = ""
    if not album:
        rows = "".join(playlist_rows) if playlist_rows else '<div class="home-playlist-empty">Nav nevienas Playlist.</div>'
        playlists_block = f"""
        <section class="home-playlists">
          <div class="home-section-head"><h2>Playlists</h2><a href="/playlists">Atvērt visas</a></div>
          <div class="home-playlist-list">{rows}</div>
        </section>"""

    root_line = f'<div class="root-line" title="{_esc(root_folder)}">{_esc(root_folder)}</div>' if root_folder else ""
    modal_open = " open" if open_new else ""

    document = f"""<!doctype html>
<html lang="lv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>My Library · LS {_esc(APP_VERSION)}</title>
<link rel="icon" type="image/x-icon" href="/ls-static/ls_web/static/LS.ico?v={_esc(APP_VERSION)}">
<link rel="stylesheet" href="/ls-static/ls_web/static/persistent_shell.css?v={_esc(APP_VERSION)}">
<script src="/ls-static/ls_web/static/persistent_shell.js?v={_esc(APP_VERSION)}" defer></script>
<style>
:root{{color-scheme:dark;--bg:#0d0d0f;--panel:#171719;--line:#29292d;--muted:#9a9aa2;--text:#f2f2f4;--accent:#efefef;--side:258px}}
*{{box-sizing:border-box}}html,body{{margin:0;min-height:100%;background:var(--bg);color:var(--text);font-family:Segoe UI,Arial,sans-serif}}body{{display:flex}}
.side{{position:fixed;inset:0 auto 0 0;width:var(--side);padding:18px 12px;border-right:1px solid #151518;background:#0b0b0d;z-index:20}}
.side-brand{{font-size:18px;font-weight:800;padding:4px 14px 18px}}.side-brand span{{font-size:12px;color:#85858d;font-weight:600}}
.side nav{{display:flex;flex-direction:column;gap:7px}}.nav-item{{height:44px;padding:0 14px;border-radius:23px;display:flex;align-items:center;gap:13px;color:#d5d5da;text-decoration:none;font-size:15px;font-weight:650}}
.nav-item:hover{{background:#1b1b1e}}.nav-item.active{{background:#2c2c2f;color:white}}.nav-icon{{width:20px;text-align:center;font-size:18px;color:#bdbdc3}}
.main{{margin-left:var(--side);width:calc(100% - var(--side));min-height:100vh;padding:26px 40px 50px}}
.top{{display:grid;grid-template-columns:minmax(280px,1fr) auto auto;gap:14px;align-items:center;position:sticky;top:0;padding-bottom:24px;background:linear-gradient(var(--bg) 75%,rgba(13,13,15,0));z-index:10}}
.search{{height:54px;border:1px solid #2b2b30;border-radius:15px;background:#19191c;color:#f6f6f6;padding:0 20px;font-size:17px;outline:none;width:100%}}.search:focus{{border-color:#56565e}}
.db-select,.new-db{{height:44px;border:1px solid #323238;border-radius:12px;background:#17171a;color:#eee;padding:0 13px;font-weight:650}}.new-db{{cursor:pointer}}
.view-toggle{{display:flex;border:1px solid #28282d;border-radius:28px;overflow:hidden;height:48px}}.view-toggle button{{width:54px;border:0;background:#111114;color:#888;font-size:21px;cursor:pointer}}.view-toggle button.active{{background:#242428;color:white}}
.library-head{{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;margin:2px 4px 22px}}.library-head h1{{font-size:28px;margin:0}}.library-head .count{{color:var(--muted)}}.root-line{{font-size:12px;color:#666;max-width:750px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:5px}}
.view-panel{{display:none}}.view-panel.visible{{display:block}}.album-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:30px 26px;align-items:start}}
.album-card{{display:block;text-decoration:none;color:white;min-width:0}}.album-cover{{width:100%;aspect-ratio:1/1;background:#18181c;border-radius:7px;overflow:hidden;box-shadow:0 1px 0 #3a3a3f inset}}.album-cover img{{width:100%;height:100%;object-fit:cover;display:block}}.cover-empty{{width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:70px;color:#45454b;background:linear-gradient(135deg,#202025,#121216)}}
.album-meta{{padding:10px 4px 0}}.album-artist{{font-size:17px;line-height:1.35;color:#f4f4f5;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.album-title{{font-size:18px;font-weight:700;line-height:1.35;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.album-count{{font-size:15px;color:#8baac8;margin-top:4px}}
.track-table-wrap{{border:1px solid #25252a;border-radius:13px;overflow:auto;background:#121214}}.track-table{{width:100%;border-collapse:collapse;min-width:980px}}.track-table th{{text-align:left;color:#97979f;background:#18181b;font-size:12px;padding:10px;border-bottom:1px solid #2b2b30;position:sticky;top:0}}.track-table td{{padding:11px 10px;border-bottom:1px solid #242429;font-size:14px;vertical-align:middle}}.track-table tr:hover td{{background:#18181c}}.path-line{{font-size:11px;color:#666;max-width:420px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-top:3px}}.none{{text-align:center;color:#888;padding:40px!important}}
.track-number-cell{{display:flex;align-items:center;gap:8px;min-width:72px}}.music-row-play{{width:30px;height:30px;border-radius:50%;border:1px solid #38383d;background:#242427;color:#f5f5f6;cursor:pointer;font-size:12px;display:inline-grid;place-items:center;flex:0 0 30px}}.music-row-play:hover{{background:#353539}}.music-track-row.is-playing td{{background:#18211c!important}}.music-track-row.is-playing .music-row-play{{background:#f4f6f5;color:#111514}}
.my-music-player{{position:fixed;left:var(--side);right:0;bottom:0;z-index:90;min-height:176px;background:#171918;color:#f1f3f2;border-top:1px solid rgba(255,255,255,.14);box-shadow:0 -10px 28px rgba(0,0,0,.28);display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);grid-template-rows:auto auto;align-items:center;gap:10px 14px;padding:10px 16px 12px}}.my-music-player.is-idle{{color:#7e8983}}.my-player-track{{grid-column:1;grid-row:2;display:flex;align-items:center;gap:11px;min-width:0}}.my-player-cover-wrap{{width:54px;height:54px;min-width:54px;border-radius:7px;overflow:hidden;background:#252827;border:1px solid rgba(255,255,255,.10);display:grid;place-items:center}}.my-player-cover{{width:100%;height:100%;object-fit:cover;display:none}}.my-player-cover-placeholder{{font-size:22px;color:#7e8983}}.my-player-copy{{min-width:0}}.my-player-title{{font-size:14px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#f1f3f2}}.my-player-source{{margin-top:4px;color:#9aa59f;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.my-player-transport,.my-player-ab{{display:flex;align-items:center;gap:7px;white-space:nowrap}}.my-player-transport{{grid-column:1/-1;grid-row:2;justify-self:center;position:relative}}.my-player-ab{{display:contents}}.my-music-player button{{background:#252827;color:#f1f3f2;border:1px solid transparent;cursor:pointer}}.my-music-player button:hover:not(:disabled){{background:#333736}}.my-music-player button:disabled{{opacity:.38;cursor:default}}.my-player-transport button{{width:36px;height:36px;border-radius:18px;font-weight:700}}.my-player-transport .my-player-play{{width:44px;height:44px;border-radius:50%;background:#f4f6f5;color:#111514;font-size:18px}}.my-player-zoom-wrap{{position:relative;display:flex;align-items:center}}.my-player-zoom-toggle{{position:relative;display:grid!important;place-items:center;padding:0!important}}.my-player-zoom-toggle svg{{width:19px;height:19px;display:block}}.my-player-zoom-badge{{position:absolute;right:2px;bottom:1px;min-width:11px;height:11px;line-height:10px;border-radius:6px;background:#147d46;color:#fff;font-size:9px;font-weight:800;text-align:center;padding:0 2px;pointer-events:none}}.my-player-zoom-menu{{position:absolute;left:50%;bottom:44px;transform:translateX(-50%);display:none;align-items:center;gap:5px;padding:6px;background:#101311;border:1px solid #343a36;border-radius:22px;box-shadow:0 8px 22px rgba(0,0,0,.36);z-index:20}}.my-player-zoom-wrap.open .my-player-zoom-menu{{display:flex}}.my-player-zoom-menu button{{width:32px;height:32px;border-radius:16px;padding:0;font-size:15px}}.my-player-zoom-menu button:hover:not(:disabled){{background:#147d46}}.my-player-loop.active,.my-player-ab button.active{{background:#147d46;color:white}}.my-player-middle{{min-width:0;grid-column:1/-1;grid-row:1}}.my-player-progress-wrap{{display:grid;grid-template-columns:minmax(200px,1fr) auto;align-items:center;gap:10px}}.my-player-progress-shell{{position:relative;height:96px;border:1px solid #404844;border-radius:8px;background:#101a1f;overflow:hidden;cursor:pointer;isolation:isolate}}.my-player-progress-shell.zoomed{{outline:2px solid rgba(44,152,255,.26);outline-offset:1px}}.my-player-waveform{{position:absolute;inset:0;width:100%;height:100%;display:block;border-radius:7px;z-index:1}}.my-player-waveform-status{{position:absolute;top:5px;right:8px;z-index:9;color:#b5c0bb;font-size:10px;pointer-events:none;text-shadow:0 1px 2px #101210;background:rgba(10,14,13,.50);border-radius:8px;padding:2px 6px}}.my-player-played-region{{position:absolute;left:0;top:0;bottom:0;width:0;background:rgba(22,108,223,.12);pointer-events:none;z-index:2;border-radius:7px 0 0 7px}}.my-player-progress{{position:absolute;inset:0;width:100%;height:100%;margin:0;opacity:0;cursor:pointer;z-index:5;-webkit-appearance:none;appearance:none}}.my-player-playhead{{position:absolute;top:0;bottom:0;left:0;width:2px;background:#2c98ff;box-shadow:0 0 0 1px rgba(8,37,69,.4);pointer-events:none;z-index:6}}.my-player-ab-region{{position:absolute;left:0;right:auto;top:0;bottom:0;background:rgba(20,125,70,.18);border-left:1px solid rgba(56,190,111,.75);border-right:1px solid rgba(56,190,111,.75);pointer-events:none;opacity:0;z-index:3}}.my-player-marker{{position:absolute;top:0;width:18px;height:96px;transform:translateX(-50%);background:transparent;pointer-events:auto;cursor:ew-resize;touch-action:none;opacity:0;z-index:8}}.my-player-marker::before{{content:'';position:absolute;left:8px;top:0;width:2px;height:96px;background:#f5d36b;border-radius:2px;box-shadow:0 0 0 1px rgba(0,0,0,.40)}}.my-player-marker::after{{position:absolute;top:2px;left:1px;min-width:16px;height:16px;line-height:16px;border-radius:9px;text-align:center;font-size:10px;font-weight:800;color:#161914;background:#f5d36b;box-shadow:0 1px 3px rgba(0,0,0,.45)}}.my-player-marker:hover::before,.my-player-marker.dragging::before{{width:3px;left:7.5px;background:#ffe27f}}.my-player-marker.dragging{{cursor:grabbing}}.my-player-marker-a::after{{content:'A'}}.my-player-marker-b::after{{content:'B'}}.my-player-time{{font-size:12px;color:#a3ada8;min-width:92px;text-align:right;font-variant-numeric:tabular-nums}}.my-player-ab button{{height:32px;border-radius:16px;padding:0 11px;font-size:12px;font-weight:700}}.my-player-ab-readout{{font-size:11px;color:#9aa59f;min-width:84px;text-align:right}}.main{{padding-bottom:218px}}
.detail-head{{display:flex;align-items:center;gap:18px;flex-wrap:wrap;margin-bottom:18px}}.detail-head h1{{margin:0;font-size:25px}}.detail-head span{{color:#92929a}}.back{{color:#b8b8c0;text-decoration:none;padding:8px 11px;border-radius:10px;background:#19191c}}
.album-detail-v2{{--album-hero:#426d58;--album-hero-dark:#355846;--album-wash:#0a2a1b;background:linear-gradient(180deg,var(--album-wash) 0,#061f14 340px);border-radius:16px 16px 0 0;overflow:hidden;min-height:620px}}
.album-hero-v2{{position:relative;display:flex;align-items:flex-end;min-height:300px;padding:44px 34px 28px;background:linear-gradient(180deg,var(--album-hero) 0,var(--album-hero-dark) 100%)}}
.album-back-v2{{position:absolute;top:16px;left:16px;width:36px;height:36px;border-radius:50%;display:grid;place-items:center;text-decoration:none;color:#fff;background:rgba(0,0,0,.30);font-size:22px;z-index:2}}
.album-back-v2:hover{{background:rgba(0,0,0,.5)}}.album-hero-inner-v2{{display:grid;grid-template-columns:220px minmax(0,1fr);gap:28px;align-items:end;width:100%}}
.album-hero-cover-v2{{width:220px;height:220px;border-radius:7px;overflow:hidden;background:#183426;box-shadow:0 12px 34px rgba(0,0,0,.34)}}.album-hero-cover-v2 img{{width:100%;height:100%;object-fit:cover;display:block}}.album-hero-cover-empty{{width:100%;height:100%;display:grid;place-items:center;font-size:64px;color:rgba(255,255,255,.28)}}
.album-hero-copy-v2{{min-width:0;padding-bottom:5px}}.album-kind-v2{{font-size:14px;font-weight:750;margin-bottom:7px}}.album-hero-copy-v2 h1{{margin:0 0 14px;font-size:clamp(38px,5vw,76px);line-height:.98;letter-spacing:-.045em;font-weight:850;overflow-wrap:anywhere}}.album-meta-v2{{font-size:14px;color:rgba(255,255,255,.82)}}.album-meta-v2 strong{{color:#fff}}
.album-actions-v2{{display:flex;align-items:center;gap:16px;min-height:82px;padding:10px 22px}}.album-play-v2{{width:58px;height:58px;border:0;border-radius:50%;background:#1ed760;color:#07160d;font-size:23px;font-weight:900;cursor:pointer;padding-left:4px;box-shadow:0 6px 18px rgba(0,0,0,.22)}}.album-play-v2:hover{{transform:scale(1.04);background:#2be16d}}.album-search-v2{{margin-left:auto;width:min(340px,45%);height:40px;border:1px solid #2d4a3b;border-radius:20px;background:#0b2a1d;color:#eef7f1;padding:0 15px;outline:none}}
.album-track-head-v2{{display:grid;grid-template-columns:34px minmax(0,1fr) 72px;gap:8px;padding:7px 22px 9px;border-bottom:1px solid rgba(255,255,255,.12);color:#98aa9f;font-size:12px}}.album-track-head-v2 span:last-child{{text-align:right;padding-right:6px}}
.album-track-list-v2{{display:flex;flex-direction:column;padding:4px 10px 24px}}.album-track-row{{display:grid;grid-template-columns:34px 34px 48px minmax(0,1fr) 72px;gap:10px;align-items:center;min-height:62px;padding:5px 12px;border-radius:9px}}.album-track-row:hover,.album-track-row.is-playing{{background:#0b3d28}}
.album-track-number{{text-align:right;color:#91a59a;font-variant-numeric:tabular-nums}}.album-row-play{{width:30px;height:30px;border-radius:50%;background:transparent;border:0;color:#dfe9e3}}.album-track-cover{{width:46px;height:46px;border-radius:7px;overflow:hidden;background:#163024;display:grid;place-items:center}}.album-track-cover img{{width:100%;height:100%;object-fit:cover;display:block}}.album-track-cover-empty{{color:#6d8277}}.album-track-copy{{min-width:0;display:flex;flex-direction:column;gap:4px}}.album-track-copy strong{{font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.album-track-copy span{{font-size:12px;color:#95a79d;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.album-track-duration{{text-align:right;color:#9caea4;font-size:13px;font-variant-numeric:tabular-nums;padding-right:6px}}
.empty-state{{margin:50px auto;max-width:620px;text-align:center;color:#aaa}}.empty-state h2{{color:#eee}}.empty-icon{{font-size:70px;color:#3e3e46}}.primary{{background:#f1f1f3;color:#111;border:0;border-radius:22px;padding:11px 18px;font-weight:750;cursor:pointer}}
.home-playlists{{margin-top:42px;padding-top:26px;border-top:1px solid #242428}}.home-section-head{{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:12px}}.home-section-head h2{{margin:0;font-size:22px}}.home-section-head a{{color:#a9a9b1;text-decoration:none;font-size:14px}}.home-section-head a:hover{{color:#fff}}.home-playlist-list{{display:flex;flex-direction:column;border:1px solid #242429;border-radius:14px;overflow:hidden;background:#121214}}.home-playlist-row{{display:grid;grid-template-columns:42px minmax(0,1fr) 28px;gap:12px;align-items:center;padding:13px 15px;color:#f1f1f3;text-decoration:none;border-bottom:1px solid #242429}}.home-playlist-row:last-child{{border-bottom:0}}.home-playlist-row:hover{{background:#19191c}}.home-playlist-icon{{width:38px;height:38px;border-radius:8px;background:#25252a;display:flex;align-items:center;justify-content:center;color:#bdbdc4;font-size:18px}}.home-playlist-copy{{display:flex;flex-direction:column;gap:3px;min-width:0}}.home-playlist-copy strong{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.home-playlist-copy span{{font-size:13px;color:#909098}}.home-playlist-arrow{{font-size:26px;color:#74747c;text-align:right}}.home-playlist-empty{{padding:26px;text-align:center;color:#85858d}}
.modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.68);z-index:100;align-items:center;justify-content:center;padding:20px}}.modal.open{{display:flex}}.modal-card{{width:min(620px,96vw);background:#1a1a1e;border:1px solid #34343a;border-radius:17px;padding:23px;box-shadow:0 24px 70px #0009}}.modal-head{{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}}.modal-head h2{{margin:0}}.modal-close{{background:#28282d;color:white;border:0;border-radius:50%;width:34px;height:34px;cursor:pointer}}
.field{{margin:14px 0}}.field label{{display:block;font-size:13px;color:#b4b4bb;margin-bottom:6px}}.field input{{width:100%;height:43px;border:1px solid #393940;border-radius:10px;background:#101012;color:white;padding:0 11px}}.folder-row{{display:grid;grid-template-columns:1fr auto;gap:9px}}.folder-row button{{border:1px solid #3a3a41;background:#252529;color:#eee;border-radius:10px;padding:0 13px;cursor:pointer}}.modal-actions{{display:flex;justify-content:flex-end;gap:9px;margin-top:20px}}.secondary{{background:#28282d;color:white;border:0;border-radius:10px;padding:10px 15px;cursor:pointer}}.status{{font-size:13px;color:#9d9da5;min-height:20px;margin-top:8px}}.status.error{{color:#ff9898}}.status.ok{{color:#8fe0a4}}
@media(max-width:1100px){{.my-music-player{{grid-template-columns:minmax(180px,1fr) auto;grid-template-rows:auto auto auto;gap:9px 10px}}.my-player-middle{{grid-column:1/-1;grid-row:1}}.my-player-track{{grid-column:1;grid-row:2}}.my-player-transport{{grid-column:2;grid-row:2}}.my-player-ab{{grid-column:1/-1;grid-row:3;justify-content:center;border-top:1px solid #2b2d2c;padding-top:8px}}.main{{padding-bottom:256px}}}}
@media(max-width:900px){{:root{{--side:205px}}.main{{padding:20px 20px 262px}}.top{{grid-template-columns:1fr auto}}.db-select{{grid-column:1/2}}.new-db{{grid-column:2/3}}.view-toggle{{position:absolute;right:0;top:62px}}.album-grid{{grid-template-columns:repeat(auto-fill,minmax(170px,1fr))}}.album-hero-v2{{padding:48px 18px 22px;min-height:245px}}.album-hero-inner-v2{{grid-template-columns:145px minmax(0,1fr);gap:18px}}.album-hero-cover-v2{{width:145px;height:145px}}.album-actions-v2{{padding-inline:14px}}.album-search-v2{{width:min(280px,58%)}}.album-track-head-v2{{padding-inline:14px}}.my-music-player{{left:var(--side);grid-template-columns:1fr auto;grid-template-rows:auto auto auto;padding:9px 11px}}.my-player-middle{{grid-column:1/-1;grid-row:1}}.my-player-track{{grid-column:1;grid-row:2}}.my-player-transport{{grid-column:2;grid-row:2}}.my-player-ab{{grid-column:1/-1;grid-row:3}}}}
</style>
</head>
<body id="ls-my-library">
{_sidebar()}
<main class="main">
  <form class="top" method="get" action="/my-library" id="search-form">
    <input type="hidden" name="db" value="{_esc(selected_name)}">
    <input type="search" class="search" name="q" value="{_esc(query)}" placeholder="Search albums, artists or songs" autocomplete="off">
    <select class="db-select" id="db-select" aria-label="Mūzikas DB">{''.join(db_options)}</select>
    <button type="button" class="new-db" id="new-db">＋ Jauna DB</button>
    <div class="view-toggle" aria-label="Skata veids">
      <button type="button" id="grid-view" class="{'active' if view == 'grid' else ''}" title="Albumu skats">▦</button>
      <button type="button" id="list-view" class="{'active' if view == 'list' else ''}" title="Saraksta skats">☷</button>
    </div>
  </form>
  <div class="library-head"><div><h1>{_esc(heading)}</h1>{root_line}</div><div class="count">{total_tracks if selected_name else 0} dziesmas</div></div>
  {detail_block if album else grid_block + list_block + playlists_block}
</main>
<div class="modal{modal_open}" id="new-db-modal" aria-hidden="{'false' if open_new else 'true'}">
  <div class="modal-card">
    <div class="modal-head"><h2>Jauna / atjaunot mūzikas DB</h2><button type="button" class="modal-close" id="modal-close">×</button></div>
    <div class="field"><label>DB nosaukums</label><input id="music-db-name" placeholder="Piemēram: Jazz, R&B & Soul"></div>
    <div class="field"><label>Mūzikas mape</label><div class="folder-row"><input id="music-db-root" placeholder="D:\\Music\\Jazz"><button type="button" id="choose-root">Izvēlēties…</button></div></div>
    <div class="field"><label>Noklusējuma žanrs (neobligāti)</label><input id="music-db-genre" placeholder="Jazz"></div>
    <div class="status" id="music-db-status"></div>
    <div class="modal-actions"><button type="button" class="secondary" id="modal-cancel">Atcelt</button><button type="button" class="primary" id="music-db-import">Izveidot / skenēt</button></div>
  </div>
</div>
<section class="my-music-player is-idle" id="my-music-player" aria-label="My Library audio player">
  <div class="my-player-middle">
    <div class="my-player-progress-wrap">
      <div class="my-player-progress-shell" title="Ctrl + mouse wheel: zoom · double click: reset zoom">
        <canvas class="my-player-waveform" id="my-player-waveform" aria-hidden="true"></canvas>
        <div class="my-player-waveform-status" id="my-player-waveform-status"></div>
        <div class="my-player-played-region" id="my-player-played-region"></div>
        <div class="my-player-ab-region" id="my-player-ab-region"></div>
        <div class="my-player-playhead" id="my-player-playhead"></div>
        <input type="range" class="my-player-progress" id="my-player-progress" min="0" max="1000" step="1" value="0" disabled aria-label="Playback position">
        <div class="my-player-marker my-player-marker-a" id="my-player-marker-a"></div><div class="my-player-marker my-player-marker-b" id="my-player-marker-b"></div>
      </div>
      <span class="my-player-time" id="my-player-time">0:00 / 0:00</span>
    </div>
  </div>
  <div class="my-player-track">
    <div class="my-player-cover-wrap"><img class="my-player-cover" id="my-player-cover" alt=""><span class="my-player-cover-placeholder" id="my-player-cover-placeholder">♪</span></div>
    <div class="my-player-copy"><div class="my-player-title" id="my-player-title">No track selected</div><div class="my-player-source" id="my-player-source">My Library</div></div>
  </div>
  <div class="my-player-transport">
    <button type="button" id="my-player-restart" disabled title="Uz dziesmas sākumu">↤</button>
    <button type="button" id="my-player-previous" disabled title="Iepriekšējā dziesma">⏮</button>
    <div class="my-player-zoom-wrap" id="my-player-zoom-wrap">
      <button type="button" class="my-player-zoom-toggle" id="my-player-zoom-toggle" data-zoom-state="in" disabled title="Zoom + · Ctrl+rullītis zoom · dubultklikšķis reset">
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M15.2 15.2 21 21" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
        <span class="zoom-symbol" id="my-player-zoom-symbol">+</span>
      </button>
    </div>
    <button type="button" class="my-player-play" id="my-player-play" disabled title="Play / Pause">▶</button>
    <button type="button" id="my-player-next" disabled title="Nākamā dziesma">⏭</button>
    <button type="button" class="my-player-loop" id="my-player-loop" disabled title="Loop whole track or A/B section" aria-pressed="false">↻</button>
    <button type="button" id="my-player-set-a" disabled>Set A</button>
    <button type="button" id="my-player-set-b" disabled>Set B</button>
    <button type="button" id="my-player-clear-ab" disabled title="Notīrīt A/B robežas">Clear AB</button>
    <span class="my-player-ab-readout" id="my-player-ab-readout"></span>
  </div>
  <audio id="my-player-audio" preload="metadata"></audio>
</section>
<script>
(() => {{
  const db = document.getElementById('db-select');
  const query = {json.dumps(query)};
  const shellNavigate = url => {{
    if (typeof window.LSShellNavigate === 'function' && window.LSShellNavigate(url)) return;
    location.href = url;
  }};

  const heroCover = document.getElementById('album-hero-cover');
  const applyAlbumTheme = () => {{
    if (!heroCover || !heroCover.naturalWidth || !heroCover.naturalHeight) return;
    try {{
      const canvas = document.createElement('canvas');
      canvas.width = 40;
      canvas.height = 40;
      const ctx = canvas.getContext('2d', {{willReadFrequently:true}});
      ctx.drawImage(heroCover, 0, 0, 40, 40);
      const pixels = ctx.getImageData(0, 0, 40, 40).data;
      const buckets = new Map();
      for (let i = 0; i < pixels.length; i += 4) {{
        if (pixels[i + 3] < 180) continue;
        const r0 = pixels[i], g0 = pixels[i + 1], b0 = pixels[i + 2];
        const max = Math.max(r0,g0,b0), min = Math.min(r0,g0,b0);
        const lum = .2126*r0 + .7152*g0 + .0722*b0;
        if (lum < 24 || (min > 222 && max > 238)) continue;
        const r = (r0 >> 4) * 16 + 8;
        const g = (g0 >> 4) * 16 + 8;
        const b = (b0 >> 4) * 16 + 8;
        const key = r + ',' + g + ',' + b;
        const saturation = (max - min) / Math.max(1,max);
        const score = 1 + saturation * 1.8 + Math.min(lum,175) / 330;
        buckets.set(key, (buckets.get(key) || 0) + score);
      }}
      let picked = [66,109,88], best = -1;
      buckets.forEach((score,key) => {{
        if (score > best) {{ best = score; picked = key.split(',').map(Number); }}
      }});
      const mix = (from,to,amount) => from.map((v,i) => Math.round(v*(1-amount)+to[i]*amount));
      const luminance = .2126*picked[0] + .7152*picked[1] + .0722*picked[2];
      const hero = mix(picked,[255,255,255],luminance < 80 ? .34 : luminance < 125 ? .24 : .16);
      const dark = hero.map(v => Math.max(0,Math.round(v*.80)));
      const wash = mix(dark,[6,31,20],.78);
      const rgb = value => 'rgb(' + value.join(',') + ')';
      const root = document.querySelector('.album-detail-v2');
      if (root) {{
        root.style.setProperty('--album-hero',rgb(hero));
        root.style.setProperty('--album-hero-dark',rgb(dark));
        root.style.setProperty('--album-wash',rgb(wash));
      }}
    }} catch (_) {{}}
  }};
  if (heroCover) {{
    if (heroCover.complete) applyAlbumTheme();
    else heroCover.addEventListener('load',applyAlbumTheme,{{once:true}});
  }}

  const albumSearch = document.getElementById('album-track-search');
  albumSearch?.addEventListener('input', () => {{
    const needle = String(albumSearch.value || '').trim().toLocaleLowerCase();
    document.querySelectorAll('.album-track-row').forEach(row => {{
      const hay = [row.dataset.playerTitle,row.dataset.playerArtist]
        .filter(Boolean).join(' ').toLocaleLowerCase();
      row.hidden = Boolean(needle && !hay.includes(needle));
    }});
  }});
  db?.addEventListener('change', () => {{
    const value = String(db.value || '').trim();
    const p = new URLSearchParams(); if (value) p.set('db', value); if (query) p.set('q', query);
    shellNavigate('/my-library' + (p.toString() ? '?' + p.toString() : ''));
  }});
  const modal = document.getElementById('new-db-modal');
  const openModal = () => {{ modal.classList.add('open'); modal.setAttribute('aria-hidden','false'); }};
  const closeModal = () => {{ modal.classList.remove('open'); modal.setAttribute('aria-hidden','true'); }};
  document.getElementById('new-db')?.addEventListener('click', openModal);
  document.getElementById('empty-new-db')?.addEventListener('click', openModal);
  document.getElementById('modal-close')?.addEventListener('click', closeModal);
  document.getElementById('modal-cancel')?.addEventListener('click', closeModal);
  modal?.addEventListener('click', e => {{ if (e.target === modal) closeModal(); }});
  document.getElementById('choose-root')?.addEventListener('click', async () => {{
    const current = document.getElementById('music-db-root').value || '';
    const r = await fetch('/choose-music-db-root?initial=' + encodeURIComponent(current), {{cache:'no-store'}});
    const data = await r.json(); if (data.ok && data.path) document.getElementById('music-db-root').value = data.path;
  }});
  document.getElementById('music-db-import')?.addEventListener('click', async () => {{
    const status = document.getElementById('music-db-status'); const button = document.getElementById('music-db-import');
    const body = new URLSearchParams({{name:document.getElementById('music-db-name').value, root_folder:document.getElementById('music-db-root').value, default_genre:document.getElementById('music-db-genre').value}});
    status.className='status'; status.textContent='Skenēju mūzikas mapi…'; button.disabled=true;
    try {{
      const r = await fetch('/music-db-import', {{method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},body:body.toString()}});
      const data = await r.json();
      if (!r.ok || !data.ok) throw new Error(data.error || 'DB izveide neizdevās.');
      status.className='status ok'; status.textContent=`Gatavs: ${{data.track_count}} dziesmas · pievienotas ${{data.added}} · atjaunotas ${{data.updated}}.`;
      setTimeout(() => shellNavigate('/my-library?db=' + encodeURIComponent(data.name)), 500);
    }} catch (e) {{ status.className='status error'; status.textContent=String(e.message || e); }} finally {{ button.disabled=false; }}
  }});
  const playerRoot = document.getElementById('my-music-player');
  const playerAudio = document.getElementById('my-player-audio');
  const playerRows = Array.from(document.querySelectorAll('.music-track-row'));
  const usesSharedShellPlayer = window.self !== window.top && document.documentElement.classList.contains('ls-shell-embedded');
  const rowToSharedTrack = row => {{
    const path = String(row?.dataset?.playerPath || '').trim();
    const title = String(row?.dataset?.playerTitle || 'Track').trim();
    const artist = String(row?.dataset?.playerArtist || '').trim();
    const album = String(row?.dataset?.playerAlbum || '').trim();
    const cover = String(row?.dataset?.playerCover || '').trim();
    return {{
      id: path || title,
      title,
      artist,
      album,
      cover,
      coverFull: cover,
      year: String(row?.dataset?.trackYear || '').trim(),
      genre: String(row?.dataset?.trackGenre || '').trim(),
      format: String(row?.dataset?.trackFormat || '').trim(),
      duration: String(row?.dataset?.trackDuration || '').trim(),
      audioUrl: path ? '/local-audio?path=' + encodeURIComponent(path) : '',
      localPath: path,
      sourceLabel: [artist, album].filter(Boolean).join(' · ') || 'My Library',
      section: 'my-library',
    }};
  }};
  const postSharedSelection = row => {{
    if (!usesSharedShellPlayer || !row) return;
    try {{
      window.parent.postMessage(
        {{type:'LS_SHELL_SELECTED_TRACK', track:rowToSharedTrack(row)}},
        window.location.origin
      );
    }} catch (_) {{}}
  }};
  const playSharedTrack = index => {{
    if (!usesSharedShellPlayer || index < 0 || index >= playerRows.length) return false;
    const items = playerRows.map(rowToSharedTrack).filter(item => item.audioUrl);
    const selected = rowToSharedTrack(playerRows[index]);
    const queueIndex = items.findIndex(item => item.id === selected.id);
    if (queueIndex < 0) return false;
    try {{
      window.parent.postMessage(
        {{type:'LS_SHELL_EXTERNAL_PLAY', items, index:queueIndex}},
        window.location.origin
      );
      return true;
    }} catch (_) {{
      return false;
    }}
  }};
  const playerPlay = document.getElementById('my-player-play');
  const playerPrevious = document.getElementById('my-player-previous');
  const playerNext = document.getElementById('my-player-next');
  const playerRestart = document.getElementById('my-player-restart');
  const playerLoop = document.getElementById('my-player-loop');
  const playerProgress = document.getElementById('my-player-progress');
  const playerWaveform = document.getElementById('my-player-waveform');
  const playerWaveformStatus = document.getElementById('my-player-waveform-status');
  const playerPlayedRegion = document.getElementById('my-player-played-region');
  const playerPlayhead = document.getElementById('my-player-playhead');
  const playerTime = document.getElementById('my-player-time');
  const playerTitle = document.getElementById('my-player-title');
  const playerSource = document.getElementById('my-player-source');
  const playerCover = document.getElementById('my-player-cover');
  const playerCoverPlaceholder = document.getElementById('my-player-cover-placeholder');
  const playerSetA = document.getElementById('my-player-set-a');
  const playerSetB = document.getElementById('my-player-set-b');
  const playerClearAB = document.getElementById('my-player-clear-ab');
  const playerABReadout = document.getElementById('my-player-ab-readout');
  const playerABRegion = document.getElementById('my-player-ab-region');
  const playerMarkerA = document.getElementById('my-player-marker-a');
  const playerMarkerB = document.getElementById('my-player-marker-b');
  const playerProgressShell = document.querySelector('.my-player-progress-shell');
  const playerZoomWrap = document.getElementById('my-player-zoom-wrap');
  const playerZoomToggle = document.getElementById('my-player-zoom-toggle');
  const playerZoomSymbol = document.getElementById('my-player-zoom-symbol');
  let currentIndex = -1;
  let abStart = null;
  let abEnd = null;
  let waveformAnalysis = null;
  let waveformState = '';
  let waveformToken = 0;
  let zoomStart = 0;
  let zoomEnd = null;
  const waveformCache = new Map();

  const getZoomWindow = () => {{
    const duration = Number(playerAudio.duration) || Number(waveformAnalysis?.duration) || 0;
    if (!(duration > 0)) return {{start:0,end:0,span:0,duration:0}};
    const start = Math.max(0, Math.min(duration, Number(zoomStart) || 0));
    const rawEnd = zoomEnd === null ? duration : Number(zoomEnd);
    const end = Math.max(start + Math.min(0.1, duration), Math.min(duration, Number.isFinite(rawEnd) ? rawEnd : duration));
    return {{start,end,span:Math.max(.001,end-start),duration}};
  }};
  const timeToZoomPercent = value => {{
    const z = getZoomWindow();
    if (!(z.span > 0)) return 0;
    return (Number(value) - z.start) / z.span * 100;
  }};
  const zoomPercentToTime = ratio => {{
    const z = getZoomWindow();
    if (!(z.span > 0)) return 0;
    return z.start + Math.max(0, Math.min(1, Number(ratio) || 0)) * z.span;
  }};
  const resetZoom = () => {{
    zoomStart = 0;
    zoomEnd = null;
    playerProgressShell?.classList.remove('zoomed');
  }};
  const syncZoomControl = mode => {{
    if (!playerZoomSymbol) return;
    const z = getZoomWindow();
    const zoomed = z.duration > 0 && z.span > 0 && z.span < z.duration - .05;
    if (mode === 'reset') playerZoomSymbol.textContent = '↺';
    else if (mode === 'out') playerZoomSymbol.textContent = '−';
    else if (mode === 'in') playerZoomSymbol.textContent = '+';
    else playerZoomSymbol.textContent = zoomed ? '−' : '+';
  }};
  const applyZoomFactor = (factor, mode='') => {{
    const z = getZoomWindow();
    if (!(z.duration > 0) || !(z.span > 0)) return;
    const centerCandidate = Number(playerAudio.currentTime);
    const center = Number.isFinite(centerCandidate) && centerCandidate >= z.start && centerCandidate <= z.end
      ? centerCandidate
      : z.start + z.span / 2;
    const newSpan = Math.max(.5, Math.min(z.duration, z.span * factor));
    if (newSpan >= z.duration - .05) {{
      resetZoom();
    }} else {{
      let start = center - newSpan / 2;
      let end = start + newSpan;
      if (start < 0) {{ end -= start; start = 0; }}
      if (end > z.duration) {{ start -= end - z.duration; end = z.duration; }}
      zoomStart = Math.max(0, start);
      zoomEnd = Math.min(z.duration, end);
      playerProgressShell?.classList.add('zoomed');
    }}
    drawWaveform();
    syncProgress();
    syncAB();
    updateWaveformStatus();
    syncZoomControl(mode);
  }};
  const updateWaveformStatus = () => {{
    if (!playerWaveformStatus) return;
    const z = getZoomWindow();
    const bits = [];
    if (waveformState) bits.push(waveformState);
    if (z.duration > 0 && z.span > 0 && z.span < z.duration - .05) bits.push('Zoom ×' + (z.duration / z.span).toFixed(1));
    const beat = waveformAnalysis?.beat;
    if (beat && Number.isFinite(beat.bpm)) bits.push('≈' + Math.round(beat.bpm) + ' BPM · 4/4');
    playerWaveformStatus.textContent = bits.join(' · ');
  }};

  const drawWaveform = () => {{
    if (!playerWaveform) return;
    const rect = playerWaveform.getBoundingClientRect();
    const cssWidth = Math.max(1, Math.round(rect.width));
    const cssHeight = Math.max(1, Math.round(rect.height));
    const dpr = Math.max(1, Math.min(2.5, window.devicePixelRatio || 1));
    const width = Math.max(1, Math.round(cssWidth * dpr));
    const height = Math.max(1, Math.round(cssHeight * dpr));
    if (playerWaveform.width !== width) playerWaveform.width = width;
    if (playerWaveform.height !== height) playerWaveform.height = height;
    const ctx = playerWaveform.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, width, height);
    ctx.save();
    ctx.scale(dpr, dpr);
    const mid = cssHeight / 2;
    const analysis = waveformAnalysis;
    const peaks = Array.isArray(analysis?.peaks) ? analysis.peaks : null;
    const duration = Number(analysis?.duration) || Number(playerAudio.duration) || 0;
    const z = getZoomWindow();

    ctx.strokeStyle = 'rgba(169,190,205,.13)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, mid + .5);
    ctx.lineTo(cssWidth, mid + .5);
    ctx.stroke();

    // Estimated beat grid: thin beat lines, stronger every fourth beat (4/4 bar).
    const beat = analysis?.beat;
    if (beat && duration > 0 && Number.isFinite(beat.bpm) && beat.bpm > 0 && Number.isFinite(beat.offset)) {{
      const period = 60 / beat.bpm;
      const pixelsPerBeat = period / Math.max(.001, z.span) * cssWidth;
      const firstIndex = Math.floor((z.start - beat.offset) / period) - 1;
      const lastIndex = Math.ceil((z.end - beat.offset) / period) + 1;
      const skipMinor = pixelsPerBeat < 3.2;
      const skipBar = pixelsPerBeat * 4 < 3.2;
      for (let index = firstIndex; index <= lastIndex; index += 1) {{
        const t = beat.offset + index * period;
        if (t < z.start - period || t > z.end + period) continue;
        const isBar = ((index % 4) + 4) % 4 === 0;
        if ((skipMinor && !isBar) || (skipBar && index % 16 !== 0)) continue;
        const x = (t - z.start) / z.span * cssWidth;
        ctx.strokeStyle = isBar ? 'rgba(214,226,235,.20)' : 'rgba(214,226,235,.075)';
        ctx.lineWidth = isBar ? 1 : .6;
        ctx.beginPath();
        ctx.moveTo(Math.round(x) + .5, 0);
        ctx.lineTo(Math.round(x) + .5, cssHeight);
        ctx.stroke();
      }}
    }}

    if (!peaks || !peaks.length || !(duration > 0)) {{
      ctx.strokeStyle = 'rgba(31,101,200,.42)';
      ctx.beginPath();
      ctx.moveTo(0, mid);
      ctx.lineTo(cssWidth, mid);
      ctx.stroke();
      ctx.restore();
      return;
    }}

    const count = peaks.length;
    const startIndex = Math.max(0, Math.floor(z.start / duration * count));
    const endIndex = Math.min(count, Math.max(startIndex + 1, Math.ceil(z.end / duration * count)));
    const visibleCount = Math.max(1, endIndex - startIndex);
    ctx.strokeStyle = 'rgba(25,113,220,.90)';
    ctx.lineWidth = .85;
    ctx.beginPath();
    for (let x = 0; x < cssWidth; x += 1) {{
      const a = startIndex + Math.floor(x / cssWidth * visibleCount);
      const b = Math.min(endIndex, startIndex + Math.ceil((x + 1) / cssWidth * visibleCount));
      let amp = 0;
      for (let i = a; i < b; i += 1) amp = Math.max(amp, Number(peaks[i]) || 0);
      amp = Math.max(.012, Math.min(1, amp));
      const half = Math.max(.75, amp * (cssHeight - 10) / 2);
      const px = x + .5;
      ctx.moveTo(px, mid - half);
      ctx.lineTo(px, mid + half);
    }}
    ctx.stroke();
    ctx.restore();
  }};

  const estimateBeatGrid = (buffer, channelData) => {{
    try {{
      const sampleRate = Number(buffer.sampleRate) || 44100;
      const length = Number(buffer.length) || 0;
      if (length < sampleRate * 8 || !channelData.length) return null;
      const blockSize = 256;
      const blockRate = sampleRate / blockSize;
      const blocks = Math.floor(length / blockSize);
      if (blocks < 256) return null;
      const envelope = new Float32Array(blocks);
      let previousFast = 0;
      let previousSlow = 0;
      for (let b = 0; b < blocks; b += 1) {{
        const start = b * blockSize;
        const end = Math.min(length, start + blockSize);
        let absSum = 0, diffSum = 0, samples = 0;
        for (let p = start + 1; p < end; p += 4) {{
          let v = 0, d = 0;
          for (let c = 0; c < channelData.length; c += 1) {{
            const cur = channelData[c][p] || 0;
            const prev = channelData[c][p-1] || 0;
            v += Math.abs(cur);
            d += Math.abs(cur - prev);
          }}
          absSum += v / channelData.length;
          diffSum += d / channelData.length;
          samples += 1;
        }}
        const raw = samples ? (absSum / samples) * .72 + (diffSum / samples) * 2.2 : 0;
        previousFast = previousFast * .55 + raw * .45;
        previousSlow = previousSlow * .94 + raw * .06;
        envelope[b] = Math.max(0, previousFast - previousSlow * .92);
      }}
      const onset = new Float32Array(blocks);
      let maxOnset = 0;
      for (let i = 2; i < blocks-2; i += 1) {{
        const local = Math.max(envelope[i], envelope[i-1]*.75, envelope[i+1]*.75);
        const value = Math.max(0, local - Math.min(envelope[i-2], envelope[i+2])*.25);
        onset[i] = value;
        if (value > maxOnset) maxOnset = value;
      }}
      if (!(maxOnset > 1e-6)) return null;
      const minBpm = 58, maxBpm = 190;
      const minLag = Math.max(2, Math.floor(blockRate * 60 / maxBpm));
      const maxLag = Math.min(blocks - 2, Math.ceil(blockRate * 60 / minBpm));
      const scored = [];
      for (let lag = minLag; lag <= maxLag; lag += 1) {{
        let cross = 0, left = 0, right = 0;
        for (let i = lag; i < blocks; i += 1) {{
          const a = onset[i], b = onset[i-lag];
          cross += a*b; left += a*a; right += b*b;
        }}
        const base = cross / Math.sqrt(Math.max(1e-12, left*right));
        const half = lag*2 <= maxLag ? 0.18 : 0;
        const dbl = Math.round(lag/2) >= minLag ? 0.10 : 0;
        let score = base;
        if (half) {{
          let c=0,l=0,r=0; const hl=lag*2;
          for (let i=hl;i<blocks;i+=1) {{const a=onset[i],b=onset[i-hl];c+=a*b;l+=a*a;r+=b*b;}}
          score += half*(c/Math.sqrt(Math.max(1e-12,l*r)));
        }}
        if (dbl) {{
          const dl=Math.max(minLag,Math.round(lag/2)); let c=0,l=0,r=0;
          for (let i=dl;i<blocks;i+=1) {{const a=onset[i],b=onset[i-dl];c+=a*b;l+=a*a;r+=b*b;}}
          score += dbl*(c/Math.sqrt(Math.max(1e-12,l*r)));
        }}
        const bpm = 60*blockRate/lag;
        const tempoPrior = 1 - Math.min(.09, Math.abs(bpm-118)/700);
        scored.push({{lag,bpm,score:score*tempoPrior}});
      }}
      scored.sort((a,b)=>b.score-a.score);
      let best = scored[0];
      if (!best || best.score < .05) return null;
      // Prefer the musically plausible octave when scores are close.
      for (const cand of scored.slice(1,12)) {{
        if (cand.score < best.score*.92) break;
        const ratio = cand.bpm / best.bpm;
        if ((best.bpm < 82 && ratio > 1.85 && ratio < 2.15) || (best.bpm > 165 && ratio > .45 && ratio < .55)) best=cand;
      }}
      const periodBlocks = best.lag;
      let bestPhase=0,bestPhaseScore=-1;
      for (let phase=0; phase<periodBlocks; phase+=1) {{
        let score=0,weight=1;
        for (let i=phase;i<blocks;i+=periodBlocks) {{
          score += onset[i]*weight;
          if (i+1<blocks) score += onset[i+1]*.55*weight;
          if (i>0) score += onset[i-1]*.55*weight;
          weight *= .9995;
        }}
        if (score>bestPhaseScore) {{bestPhaseScore=score;bestPhase=phase;}}
      }}
      // Sub-block phase refinement around the strongest nearby transient.
      const coarseTime = bestPhase/blockRate;
      const period = 60/best.bpm;
      let offset = coarseTime;
      let refineScore=-1;
      for (let delta=-.06; delta<=.0601; delta+=.005) {{
        const candidate=Math.max(0,coarseTime+delta); let score=0;
        for (let t=candidate;t<Math.min(Number(buffer.duration)||0,180);t+=period) {{
          const idx=Math.max(0,Math.min(blocks-1,Math.round(t*blockRate)));
          score+=onset[idx];
        }}
        if(score>refineScore){{refineScore=score;offset=candidate;}}
      }}
      const median=scored[Math.floor(Math.min(scored.length-1,scored.length*.5))]?.score||.0001;
      return {{bpm:best.bpm,offset,confidence:best.score/Math.max(.0001,median)}};
    }} catch (_) {{ return null; }}
  }};

  const computeWaveformAnalysis = async url => {{
    if (!url) return {{peaks:[],duration:0,beat:null}};
    if (waveformCache.has(url)) return waveformCache.get(url);
    const response = await fetch(url, {{cache:'force-cache'}});
    if (!response.ok) throw new Error('waveform fetch failed');
    const bytes = await response.arrayBuffer();
    const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextCtor) throw new Error('AudioContext unavailable');
    const context = new AudioContextCtor();
    try {{
      const buffer = await context.decodeAudioData(bytes.slice(0));
      const channels = Math.min(2, buffer.numberOfChannels || 1);
      const length = buffer.length || 0;
      if (!length) return {{peaks:[],duration:Number(buffer.duration)||0,beat:null}};
      const bins = Math.min(32768, Math.max(4096, Math.floor(length / 128)));
      const step = Math.max(1, Math.ceil(length / bins));
      const peaks = new Array(bins).fill(0);
      const channelData = [];
      for (let c = 0; c < channels; c += 1) channelData.push(buffer.getChannelData(c));
      for (let i = 0; i < bins; i += 1) {{
        const start = i * step;
        const end = Math.min(length, start + step);
        let peak = 0;
        for (let p = start; p < end; p += 1) {{
          for (let c = 0; c < channelData.length; c += 1) {{
            const value = Math.abs(channelData[c][p] || 0);
            if (value > peak) peak = value;
          }}
        }}
        peaks[i] = peak;
      }}
      const sorted = peaks.slice().sort((a,b)=>a-b);
      const reference = Math.max(sorted[Math.floor(sorted.length * .995)] || 0, .0001);
      const normalized = peaks.map(value => Math.min(1, Math.pow(value / reference, .86)));
      const analysis = {{
        peaks:normalized,
        duration:Number(buffer.duration)||0,
        beat:estimateBeatGrid(buffer,channelData),
      }};
      waveformCache.set(url, analysis);
      return analysis;
    }} finally {{
      try {{ await context.close(); }} catch (_) {{}}
    }}
  }};

  const loadWaveform = url => {{
    const token = ++waveformToken;
    waveformAnalysis = null;
    waveformState = url ? 'waveform…' : '';
    resetZoom();
    drawWaveform();
    updateWaveformStatus();
    if (!url) return;
    computeWaveformAnalysis(url).then(analysis => {{
      if (token !== waveformToken) return;
      waveformAnalysis = analysis;
      waveformState = analysis?.peaks?.length ? 'waveform ready' : '';
      drawWaveform();
      updateWaveformStatus();
      syncProgress();
      syncAB();
    }}).catch(() => {{
      if (token !== waveformToken) return;
      waveformAnalysis = null;
      waveformState = 'waveform unavailable';
      drawWaveform();
      updateWaveformStatus();
    }});
  }};
  if (window.ResizeObserver && playerWaveform) new ResizeObserver(() => {{drawWaveform();syncProgress();syncAB();}}).observe(playerWaveform);

  const formatTime = value => {{
    const seconds = Math.max(0, Number(value) || 0);
    const whole = Math.floor(seconds);
    return Math.floor(whole / 60) + ':' + String(whole % 60).padStart(2, '0');
  }};
  const hasAB = () => Number.isFinite(abStart) && Number.isFinite(abEnd) && abEnd > abStart;
  const syncAB = () => {{
    const duration = Number(playerAudio.duration) || Number(waveformAnalysis?.duration) || 0;
    const z = getZoomWindow();
    playerSetA?.classList.toggle('active', Number.isFinite(abStart));
    playerSetB?.classList.toggle('active', Number.isFinite(abEnd));
    if (playerABReadout) {{
      if (hasAB()) playerABReadout.textContent = `A/B ${{formatTime(abStart)}}–${{formatTime(abEnd)}}`;
      else if (Number.isFinite(abStart)) playerABReadout.textContent = `A ${{formatTime(abStart)}}`;
      else if (Number.isFinite(abEnd)) playerABReadout.textContent = `B ${{formatTime(abEnd)}}`;
      else playerABReadout.textContent = '';
    }}
    if (playerClearAB) playerClearAB.disabled = !(Number.isFinite(abStart) || Number.isFinite(abEnd));
    if (!(duration > 0) || !(z.span > 0)) return;
    const setPos = (node, value) => {{
      if (!node) return;
      if (Number.isFinite(value) && value >= z.start && value <= z.end) {{
        node.style.left = timeToZoomPercent(value) + '%';
        node.style.opacity = '1';
      }} else node.style.opacity = '0';
    }};
    setPos(playerMarkerA, abStart);
    setPos(playerMarkerB, abEnd);
    if (playerABRegion) {{
      if (hasAB() && abEnd > z.start && abStart < z.end) {{
        const leftTime = Math.max(abStart, z.start);
        const rightTime = Math.min(abEnd, z.end);
        playerABRegion.style.left = timeToZoomPercent(leftTime) + '%';
        playerABRegion.style.width = Math.max(0, timeToZoomPercent(rightTime) - timeToZoomPercent(leftTime)) + '%';
        playerABRegion.style.opacity = '1';
      }} else playerABRegion.style.opacity = '0';
    }}
  }};
  const clearAB = () => {{ abStart = null; abEnd = null; syncAB(); }};
  const syncLoop = () => {{
    const active = Boolean(playerLoop?.classList.contains('active'));
    if (playerAudio) playerAudio.loop = active && !hasAB();
    if (playerLoop) {{ playerLoop.setAttribute('aria-pressed', active ? 'true' : 'false'); playerLoop.title = active ? 'Loop ON — whole track or A/B section' : 'Loop whole track or A/B section'; }}
  }};
  const syncProgress = () => {{
    const duration = Number(playerAudio.duration) || Number(waveformAnalysis?.duration) || 0;
    const current = Number(playerAudio.currentTime) || 0;
    const z = getZoomWindow();
    const rawPct = z.span > 0 ? (current - z.start) / z.span * 100 : 0;
    const progressPct = Math.max(0, Math.min(100, rawPct));
    if (playerProgress) playerProgress.value = z.span > 0 ? String(Math.round(progressPct / 100 * 1000)) : '0';
    if (playerPlayhead) {{
      playerPlayhead.style.left = progressPct + '%';
      playerPlayhead.style.opacity = rawPct >= 0 && rawPct <= 100 ? '1' : '0';
    }}
    if (playerPlayedRegion) playerPlayedRegion.style.width = progressPct + '%';
    if (playerTime) playerTime.textContent = `${{formatTime(current)}} / ${{formatTime(duration)}}`;
    if (playerAudio && !playerAudio.paused && playerLoop?.classList.contains('active') && hasAB() && current >= abEnd - 0.035) {{
      playerAudio.currentTime = abStart;
    }}
  }};
  const syncPlayState = () => {{
    const playing = currentIndex >= 0 && !playerAudio.paused;
    if (playerPlay) playerPlay.textContent = playing ? '❚❚' : '▶';
    playerRows.forEach((row, index) => {{
      row.classList.toggle('is-playing', index === currentIndex && playing);
      const button = row.querySelector('.music-row-play');
      if (button) button.textContent = index === currentIndex && playing ? '❚❚' : '▶';
    }});
  }};
  const enablePlayer = enabled => {{
    [playerPlay, playerPrevious, playerNext, playerRestart, playerLoop, playerProgress, playerSetA, playerSetB, playerZoomToggle].forEach(node => {{ if (node) node.disabled = !enabled; }});
    if (playerClearAB) playerClearAB.disabled = true;
    playerRoot?.classList.toggle('is-idle', !enabled);
  }};
  const loadTrack = async (index, autoplay=true) => {{
    if (index < 0 || index >= playerRows.length) return;
    const row = playerRows[index];
    const path = String(row.dataset.playerPath || '').trim();
    if (!path) return;
    currentIndex = index;
    clearAB();
    const title = String(row.dataset.playerTitle || 'Track');
    const artist = String(row.dataset.playerArtist || '');
    const album = String(row.dataset.playerAlbum || '');
    const cover = String(row.dataset.playerCover || '');
    postSharedSelection(row);
    if (usesSharedShellPlayer && playSharedTrack(index)) return;
    playerTitle.textContent = title;
    playerSource.textContent = [artist, album].filter(Boolean).join(' · ') || 'My Library';
    if (cover) {{ playerCover.src = cover; playerCover.style.display = 'block'; playerCoverPlaceholder.style.display = 'none'; }} else {{ playerCover.removeAttribute('src'); playerCover.style.display = 'none'; playerCoverPlaceholder.style.display = 'inline'; }}
    playerAudio.src = '/local-audio?path=' + encodeURIComponent(path);
    playerAudio.load();
    loadWaveform(playerAudio.src);
    enablePlayer(true);
    syncLoop();
    if (autoplay) {{ try {{ await playerAudio.play(); }} catch (_) {{}} }}
    syncPlayState();
  }};
  playerRows.forEach((row, index) => {{
    row.querySelector('.music-row-play')?.addEventListener('click', event => {{
      event.preventDefault(); event.stopPropagation();
      if (usesSharedShellPlayer) {{
        postSharedSelection(row);
        playSharedTrack(index);
        return;
      }}
      if (currentIndex === index && !playerAudio.paused) playerAudio.pause();
      else if (currentIndex === index && playerAudio.src) playerAudio.play().catch(() => {{}});
      else loadTrack(index, true);
    }});
    row.addEventListener('click', event => {{
      if (!event.target.closest('button')) postSharedSelection(row);
    }});
    row.addEventListener('dblclick', event => {{
      if (!event.target.closest('button')) {{
        if (usesSharedShellPlayer) playSharedTrack(index);
        else loadTrack(index, true);
      }}
    }});
  }});
  document.getElementById('album-play-all')?.addEventListener('click', () => {{
    const visibleIndex = playerRows.findIndex(row => row.classList.contains('album-track-row') && !row.hidden);
    if (visibleIndex >= 0) {{
      if (usesSharedShellPlayer) playSharedTrack(visibleIndex);
      else loadTrack(visibleIndex, true);
    }}
  }});
  playerPlay?.addEventListener('click', () => {{
    if (currentIndex < 0) {{ if (playerRows.length) loadTrack(0, true); return; }}
    if (playerAudio.paused) playerAudio.play().catch(() => {{}}); else playerAudio.pause();
  }});
  playerRestart?.addEventListener('click', () => {{ if (currentIndex >= 0) playerAudio.currentTime = hasAB() ? abStart : 0; }});
  playerPrevious?.addEventListener('click', () => {{ if (playerRows.length) loadTrack((currentIndex - 1 + playerRows.length) % playerRows.length, true); }});
  playerZoomToggle?.addEventListener('click', event => {{
    event.preventDefault();
    const state = playerZoomToggle.dataset.zoomState || 'in';
    if (state === 'out') applyZoomFactor(1.62, 'out');
    else if (state === 'reset') {{ resetZoom(); drawWaveform(); syncProgress(); syncAB(); updateWaveformStatus(); syncZoomControl('reset'); }}
    else applyZoomFactor(.62, 'in');
  }});
  playerZoomToggle?.addEventListener('dblclick', event => {{
    event.preventDefault();
    resetZoom(); drawWaveform(); syncProgress(); syncAB(); updateWaveformStatus(); syncZoomControl('reset');
  }});
  playerNext?.addEventListener('click', () => {{ if (playerRows.length) loadTrack((currentIndex + 1) % playerRows.length, true); }});
  playerLoop?.addEventListener('click', () => {{ playerLoop.classList.toggle('active'); syncLoop(); }});
  playerSetA?.addEventListener('click', () => {{ abStart = Number(playerAudio.currentTime) || 0; if (Number.isFinite(abEnd) && abEnd <= abStart) abEnd = null; syncAB(); syncLoop(); }});
  playerSetB?.addEventListener('click', () => {{
    const value = Math.max(0, Number(playerAudio.currentTime) || 0);
    abEnd = value;
    if (Number.isFinite(abStart) && abEnd <= abStart) {{ const oldA = abStart; abStart = abEnd; abEnd = oldA; }}
    syncAB(); syncLoop();
  }});
  playerClearAB?.addEventListener('click', () => {{ clearAB(); syncLoop(); }});
  const dragMarker = (node, marker) => {{
    if (!node) return;
    let activePointer = null;
    const valueFromPointer = event => {{
      const duration = Number(playerAudio.duration) || 0;
      const rect = playerProgressShell?.getBoundingClientRect();
      if (!(duration > 0) || !rect || rect.width <= 0) return null;
      const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
      return zoomPercentToTime(ratio);
    }};
    const move = event => {{
      if (activePointer !== event.pointerId) return;
      const value = valueFromPointer(event);
      if (!Number.isFinite(value)) return;
      if (marker === 'a') {{
        const upper = Number.isFinite(abEnd) ? Math.max(0, abEnd - 0.05) : Number(playerAudio.duration) || value;
        abStart = Math.max(0, Math.min(value, upper));
      }} else {{
        const lower = Number.isFinite(abStart) ? Math.min(Number(playerAudio.duration) || value, abStart + 0.05) : 0;
        abEnd = Math.max(lower, Math.min(value, Number(playerAudio.duration) || value));
      }}
      syncAB(); syncLoop();
      event.preventDefault();
    }};
    const finish = event => {{
      if (activePointer !== event.pointerId) return;
      activePointer = null;
      node.classList.remove('dragging');
      try {{ node.releasePointerCapture(event.pointerId); }} catch (_) {{}}
      event.preventDefault();
    }};
    node.addEventListener('pointerdown', event => {{
      if (!Number.isFinite(marker === 'a' ? abStart : abEnd)) return;
      activePointer = event.pointerId;
      node.classList.add('dragging');
      try {{ node.setPointerCapture(event.pointerId); }} catch (_) {{}}
      move(event);
      event.preventDefault();
      event.stopPropagation();
    }});
    node.addEventListener('pointermove', move);
    node.addEventListener('pointerup', finish);
    node.addEventListener('pointercancel', finish);
  }};
  dragMarker(playerMarkerA, 'a');
  dragMarker(playerMarkerB, 'b');
  playerProgress?.addEventListener('input', () => {{ const z = getZoomWindow(); if (z.span > 0) playerAudio.currentTime = zoomPercentToTime(Number(playerProgress.value || 0) / 1000); }});
  playerProgressShell?.addEventListener('wheel', event => {{
    const duration = Number(playerAudio.duration) || Number(waveformAnalysis?.duration) || 0;
    if (!(duration > 0) || !event.ctrlKey) return;
    event.preventDefault();
    event.stopPropagation();
    const rect = playerProgressShell.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (event.clientX - rect.left) / Math.max(1, rect.width)));
    const z = getZoomWindow();
    const center = z.start + pct * z.span;
    const factor = event.deltaY < 0 ? .72 : 1.38;
    const newSpan = Math.max(.5, Math.min(duration, z.span * factor));
    let newStart = center - pct * newSpan;
    let newEnd = newStart + newSpan;
    if (newStart < 0) {{ newEnd -= newStart; newStart = 0; }}
    if (newEnd > duration) {{ newStart -= newEnd - duration; newEnd = duration; }}
    newStart = Math.max(0, newStart);
    newEnd = Math.min(duration, newEnd);
    if (newSpan >= duration - .05) resetZoom();
    else {{
      zoomStart = newStart;
      zoomEnd = newEnd;
      playerProgressShell.classList.add('zoomed');
    }}
    drawWaveform();
    syncProgress();
    syncAB();
    updateWaveformStatus();
    syncZoomControl(event.deltaY < 0 ? 'in' : 'out');
  }}, {{passive:false}});
  playerProgressShell?.addEventListener('dblclick', event => {{
    event.preventDefault();
    resetZoom();
    drawWaveform();
    syncProgress();
    syncAB();
    updateWaveformStatus();
    syncZoomControl('reset');
  }});
  playerAudio.addEventListener('play', syncPlayState);
  playerAudio.addEventListener('pause', syncPlayState);
  playerAudio.addEventListener('loadedmetadata', () => {{ if (zoomEnd !== null && zoomEnd > playerAudio.duration) resetZoom(); drawWaveform(); syncProgress(); syncAB(); updateWaveformStatus(); }});
  playerAudio.addEventListener('durationchange', () => {{ drawWaveform(); syncProgress(); syncAB(); updateWaveformStatus(); }});
  playerAudio.addEventListener('timeupdate', syncProgress);
  playerAudio.addEventListener('seeking', syncProgress);
  playerAudio.addEventListener('ended', () => {{
    if (playerLoop?.classList.contains('active') && hasAB()) {{ playerAudio.currentTime = abStart; playerAudio.play().catch(() => {{}}); return; }}
    if (!playerLoop?.classList.contains('active') && currentIndex >= 0 && currentIndex + 1 < playerRows.length) loadTrack(currentIndex + 1, true);
    else syncPlayState();
  }});
  enablePlayer(false);
  drawWaveform();
  updateWaveformStatus();
  syncZoomControl();

  const setView = view => {{
    const p = new URLSearchParams(location.search);
    p.delete('ls_embedded');
    p.set('view', view);
    shellNavigate('/my-library?' + p.toString());
  }};
  document.getElementById('grid-view')?.addEventListener('click', () => setView('grid'));
  document.getElementById('list-view')?.addEventListener('click', () => setView('list'));
}})();
</script>
</body></html>"""
    return document.encode("utf-8")