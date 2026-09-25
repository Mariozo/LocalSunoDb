import html
import urllib.parse

from ls_core.runtime import APP_VERSION
from ls_data.music_library import list_music_databases, search_music_database


def _esc(value):
    return html.escape(str(value or ""), quote=True)


def _duration_text(value):
    try:
        seconds = int(round(float(value or 0)))
    except Exception:
        return ""
    if seconds <= 0:
        return ""
    return f"{seconds // 60}:{seconds % 60:02d}"


def _track_text(row):
    disc = row.get("disc_no")
    track = row.get("track_no")
    parts = []
    if disc:
        parts.append(f"CD {int(disc)}")
    if track:
        total = row.get("track_total")
        parts.append(
            f"{int(track)}" + (f"/{int(total)}" if total else "")
        )
    return " · ".join(parts)


def render_music_database_page(name="", query=""):
    catalog = list_music_databases().get("databases") or []
    usable = [item for item in catalog if not item.get("error")]
    requested = str(name or "").strip()
    selected = None
    if requested:
        selected = next(
            (item for item in usable if str(item.get("name") or "") == requested),
            None,
        )
    if selected is None and usable:
        selected = usable[0]

    options = ['<option value="">— izvēlies DB —</option>']
    for item in usable:
        db_name = str(item.get("name") or "")
        selected_attr = " selected" if selected and db_name == str(selected.get("name") or "") else ""
        options.append(
            f'<option value="{_esc(db_name)}"{selected_attr}>{_esc(db_name)}'
            f' · {int(item.get("track_count") or 0)} dziesmas</option>'
        )

    data = {
        "name": "",
        "root_folder": "",
        "total": 0,
        "shown": 0,
        "rows": [],
        "query": str(query or "").strip(),
    }
    if selected:
        data = search_music_database(
            str(selected.get("name") or ""),
            query=query,
            limit=500,
        )

    rows_html = []
    db_name = str(data.get("name") or "")
    for row in data.get("rows") or []:
        cover_sha1 = str(row.get("cover_sha1") or "").strip()
        if cover_sha1 and db_name:
            cover_url = (
                "/music-db-cover?name="
                + urllib.parse.quote(db_name)
                + "&sha1="
                + urllib.parse.quote(cover_sha1)
            )
            cover = f'<img class="music-cover" src="{_esc(cover_url)}" alt="">'
        else:
            cover = '<div class="music-cover music-cover-empty">♪</div>'

        artist = str(row.get("artist") or row.get("album_artist") or "").strip()
        title = str(row.get("title") or "").strip()
        album = str(row.get("album") or "").strip()
        year = str(row.get("year") or "").strip()
        genre = str(row.get("genre") or "").strip()
        track_text = _track_text(row)
        duration = _duration_text(row.get("duration_seconds"))
        fmt = str(row.get("format") or "").upper()
        path = str(row.get("path") or "")

        rows_html.append(
            "<tr>"
            f'<td class="cover-cell">{cover}</td>'
            f'<td class="artist-cell">{_esc(artist)}</td>'
            f'<td class="year-cell">{_esc(year)}</td>'
            f'<td class="album-cell">{_esc(album)}</td>'
            f'<td class="track-cell">{_esc(track_text)}</td>'
            f'<td class="title-cell"><strong>{_esc(title)}</strong>'
            f'<div class="path-line" title="{_esc(path)}">{_esc(path)}</div></td>'
            f'<td class="genre-cell">{_esc(genre)}</td>'
            f'<td class="format-cell">{_esc(fmt)}</td>'
            f'<td class="duration-cell">{_esc(duration)}</td>'
            "</tr>"
        )

    if not rows_html:
        rows_html.append(
            '<tr><td colspan="9" class="empty-cell">'
            + (
                "Nekas nav atrasts."
                if selected
                else "Nav nevienas atsevišķas mūzikas DB. Izveido to sadaļā Rīki → Izveidot / piepildīt DB…"
            )
            + "</td></tr>"
        )

    selected_name = str(data.get("name") or "")
    query_value = str(data.get("query") or "")
    count_text = (
        f"{int(data.get('shown') or 0)} no {int(data.get('total') or 0)}"
        if selected
        else "0"
    )

    document = f"""<!doctype html>
<html lang="lv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mūzikas DB · LS { _esc(APP_VERSION) }</title>
<link rel="icon" type="image/x-icon" href="/ls-static/ls_web/static/LS.ico?v={_esc(APP_VERSION)}">
<style>
:root{{color-scheme:dark}}
*{{box-sizing:border-box}}
body{{margin:0;background:#0d0d10;color:#f1f1f3;font-family:Segoe UI,Arial,sans-serif}}
.music-shell{{min-height:100vh}}
.music-topbar{{height:62px;display:flex;align-items:center;gap:24px;padding:0 24px;border-bottom:1px solid #2b2b31;background:#121216;position:sticky;top:0;z-index:10}}
.music-brand{{font-size:21px;font-weight:800;color:#fff;text-decoration:none}}
.music-topbar a{{color:#d9d9de;text-decoration:none}}
.music-topbar a:hover{{color:#fff}}
.music-main{{padding:22px 26px 40px}}
.music-head{{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;flex-wrap:wrap;margin-bottom:18px}}
.music-head h1{{margin:0;font-size:30px}}
.music-root{{color:#9c9ca4;font-size:13px;margin-top:5px;word-break:break-all}}
.music-count{{color:#aaa;font-size:14px}}
.music-controls{{display:grid;grid-template-columns:minmax(180px,280px) minmax(260px,1fr) auto;gap:10px;margin-bottom:18px}}
.music-controls select,.music-controls input,.music-controls button{{background:#1b1b20;color:#f2f2f4;border:1px solid #34343a;border-radius:9px;padding:10px 12px;font-size:14px}}
.music-controls button{{cursor:pointer;font-weight:700}}
.music-controls button:hover{{background:#25252b}}
.music-table-wrap{{overflow:auto;border:1px solid #26262b;border-radius:12px;background:#111114}}
.music-table{{width:100%;border-collapse:collapse;min-width:1100px}}
.music-table th{{position:sticky;top:62px;background:#17171b;color:#a9a9b1;text-align:left;font-size:12px;font-weight:700;padding:9px 10px;border-bottom:1px solid #303037;z-index:5}}
.music-table td{{padding:9px 10px;border-bottom:1px solid #24242a;vertical-align:middle;font-size:14px}}
.music-table tr:hover td{{background:#17171c}}
.cover-cell{{width:58px}}
.music-cover{{display:block;width:44px;height:44px;object-fit:cover;border-radius:7px;background:#25252a}}
.music-cover-empty{{display:flex;align-items:center;justify-content:center;color:#777;font-size:22px}}
.artist-cell{{width:190px;font-weight:600}}
.year-cell{{width:75px;color:#bbb}}
.album-cell{{width:220px}}
.track-cell{{width:88px;color:#bbb}}
.title-cell{{min-width:280px}}
.path-line{{margin-top:3px;color:#6f6f78;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:520px}}
.genre-cell{{width:130px;color:#c5c5cb}}
.format-cell,.duration-cell{{width:72px;color:#aaa}}
.empty-cell{{padding:38px!important;text-align:center;color:#999}}
@media(max-width:800px){{.music-controls{{grid-template-columns:1fr}}.music-main{{padding:16px}}}}
</style>
</head>
<body>
<div class="music-shell">
<header class="music-topbar">
  <a class="music-brand" href="/">LS</a>
  <a href="/">Suno Library</a>
  <a href="/playlists">Playlists</a>
  <strong>Mūzikas DB</strong>
</header>
<main class="music-main">
  <section class="music-head">
    <div>
      <h1>{_esc(selected_name or "Mūzikas DB")}</h1>
      <div class="music-root">{_esc(data.get("root_folder") or "")}</div>
    </div>
    <div class="music-count">{_esc(count_text)}</div>
  </section>
  <form class="music-controls" method="get" action="/music-db">
    <select name="name" id="music-db-browser-select">{''.join(options)}</select>
    <input type="search" name="q" value="{_esc(query_value)}" placeholder="Meklēt Artist / Album / Title / Year / Genre…" autocomplete="off">
    <button type="submit">Meklēt</button>
  </form>
  <div class="music-table-wrap">
    <table class="music-table">
      <thead>
        <tr>
          <th></th><th>Autors</th><th>Gads</th><th>Albums</th><th>Nr.</th>
          <th>Nosaukums</th><th>Žanrs</th><th>Tips</th><th>Ilgums</th>
        </tr>
      </thead>
      <tbody>{''.join(rows_html)}</tbody>
    </table>
  </div>
</main>
</div>
<script>
(() => {{
  const select = document.getElementById("music-db-browser-select");
  if (!select) return;
  select.addEventListener("change", () => {{
    const value = String(select.value || "").trim();
    window.location.href = value ? "/music-db?name=" + encodeURIComponent(value) : "/music-db";
  }});
}})();
</script>
</body>
</html>"""
    return document.encode("utf-8")
