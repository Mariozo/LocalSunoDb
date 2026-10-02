"""Standalone non-Suno music databases.

These databases are intentionally separate from Data/local_suno.db.  The module
catalogs files only; it never moves, renames, edits, or deletes user audio.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path

from ls_core.runtime import DATA_DIR

MUSIC_DB_DIR = DATA_DIR / "MusicDB"
SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".m4a", ".aac", ".ogg"}
_YEAR_RE = re.compile(r"(?<!\d)(18|19|20|21)\d{2}(?!\d)")
_LEADING_ORDER_RE = re.compile(r"^\s*(?:[\[(]\s*)?\d{1,4}(?:\s*[\])])?\s*[-._]\s*")
_ALBUM_FOLDER_PATTERNS = (
    re.compile(r"^\s*\[(?P<year>\d{4})\]\s*-\s*(?P<artist>.+?)\s*-\s*(?P<album>.+?)\s*$"),
    re.compile(r"^\s*(?P<year>\d{4})\s*-\s*(?P<artist>.+?)\s*-\s*(?P<album>.+?)\s*$"),
)


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_name(value):
    text = unicodedata.normalize("NFKC", str(value or "")).strip()
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    if not text:
        raise ValueError("DB nosaukums nevar būt tukšs.")
    return text[:100]


def _db_path(name):
    MUSIC_DB_DIR.mkdir(parents=True, exist_ok=True)
    return MUSIC_DB_DIR / f"{_safe_name(name)}.db"


def _connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _schema_is_music_db(conn):
    names = {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if not {"library_info", "covers", "tracks"}.issubset(names):
        return False
    cols = {
        str(row[1])
        for row in conn.execute("PRAGMA table_info(tracks)")
    }
    return {"path", "title", "artist", "album", "year", "genre", "cover_sha1"}.issubset(cols)


def _ensure_schema(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS library_info (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS covers (
            sha1 TEXT PRIMARY KEY,
            mime_type TEXT NOT NULL DEFAULT '',
            image_data BLOB NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tracks (
            id INTEGER PRIMARY KEY,
            path TEXT NOT NULL COLLATE NOCASE UNIQUE,
            filename TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            artist TEXT NOT NULL DEFAULT '',
            album_artist TEXT NOT NULL DEFAULT '',
            album TEXT NOT NULL DEFAULT '',
            year INTEGER,
            track_no INTEGER,
            track_total INTEGER,
            disc_no INTEGER,
            disc_total INTEGER,
            genre TEXT NOT NULL DEFAULT '',
            duration_seconds REAL,
            format TEXT NOT NULL DEFAULT '',
            size_bytes INTEGER NOT NULL DEFAULT 0,
            modified_time TEXT NOT NULL DEFAULT '',
            cover_sha1 TEXT,
            imported_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(cover_sha1) REFERENCES covers(sha1) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_music_tracks_artist_album
            ON tracks(artist COLLATE NOCASE, year, album COLLATE NOCASE, disc_no, track_no, title COLLATE NOCASE);
        CREATE INDEX IF NOT EXISTS idx_music_tracks_album
            ON tracks(album COLLATE NOCASE, disc_no, track_no, title COLLATE NOCASE);
        CREATE INDEX IF NOT EXISTS idx_music_tracks_genre
            ON tracks(genre COLLATE NOCASE, artist COLLATE NOCASE, album COLLATE NOCASE);
        """
    )


def _set_info(conn, key, value):
    conn.execute(
        "INSERT OR REPLACE INTO library_info(key, value) VALUES (?, ?)",
        (str(key), str(value or "")),
    )


def _read_info(conn):
    return {
        str(row["key"]): str(row["value"] or "")
        for row in conn.execute("SELECT key, value FROM library_info")
    }


def _syncsafe(raw):
    if len(raw) != 4:
        return 0
    return ((raw[0] & 0x7F) << 21) | ((raw[1] & 0x7F) << 14) | ((raw[2] & 0x7F) << 7) | (raw[3] & 0x7F)


def _decode_text(payload):
    if not payload:
        return ""
    encoding = payload[0]
    data = payload[1:]
    codec = {0: "latin-1", 1: "utf-16", 2: "utf-16-be", 3: "utf-8"}.get(encoding, "utf-8")
    try:
        value = data.decode(codec, errors="replace")
    except Exception:
        value = data.decode("utf-8", errors="replace")
    return value.replace("\x00", " / ").strip(" \t\r\n/")


def _skip_terminated(data, start, encoding):
    if encoding in (1, 2):
        pos = start
        while pos + 1 < len(data):
            if data[pos:pos + 2] == b"\x00\x00":
                return pos + 2
            pos += 2
        return len(data)
    pos = data.find(b"\x00", start)
    return len(data) if pos < 0 else pos + 1


def _parse_apic(payload):
    if len(payload) < 4:
        return None
    encoding = payload[0]
    mime_end = payload.find(b"\x00", 1)
    if mime_end < 0 or mime_end + 1 >= len(payload):
        return None
    mime = payload[1:mime_end].decode("latin-1", errors="replace").strip() or "image/jpeg"
    image_start = _skip_terminated(payload, mime_end + 2, encoding)
    image = payload[image_start:]
    return (mime, image) if image else None


def _split_number(value):
    text = str(value or "").strip()
    if not text:
        return None, None
    parts = text.split("/", 1)
    try:
        current = int(re.match(r"\d+", parts[0].strip()).group(0))
    except Exception:
        current = None
    try:
        total = int(re.match(r"\d+", parts[1].strip()).group(0)) if len(parts) > 1 else None
    except Exception:
        total = None
    return current, total


def _year(value):
    match = _YEAR_RE.search(str(value or ""))
    return int(match.group(0)) if match else None


def _read_id3v2(path):
    values = {}
    cover = None
    try:
        with path.open("rb") as handle:
            header = handle.read(10)
            if len(header) != 10 or header[:3] != b"ID3":
                return values, cover
            version = header[3]
            data = handle.read(_syncsafe(header[6:10]))
    except Exception:
        return values, cover

    pos = 0
    while pos < len(data):
        if version == 2:
            if pos + 6 > len(data):
                break
            frame_id = data[pos:pos + 3].decode("latin-1", errors="ignore")
            size = int.from_bytes(data[pos + 3:pos + 6], "big")
            header_size = 6
            frame_id = {"TT2":"TIT2","TP1":"TPE1","TP2":"TPE2","TAL":"TALB","TYE":"TYER","TRK":"TRCK","TPA":"TPOS","TCO":"TCON"}.get(frame_id, frame_id)
        else:
            if pos + 10 > len(data):
                break
            raw_id = data[pos:pos + 4]
            if raw_id == b"\x00\x00\x00\x00":
                break
            frame_id = raw_id.decode("latin-1", errors="ignore")
            raw_size = data[pos + 4:pos + 8]
            size = _syncsafe(raw_size) if version >= 4 else int.from_bytes(raw_size, "big")
            header_size = 10
        if not frame_id.strip("\x00") or size <= 0:
            break
        start, end = pos + header_size, pos + header_size + size
        if end > len(data):
            break
        payload = data[start:end]
        pos = end
        if frame_id in {"TIT2","TPE1","TPE2","TALB","TDRC","TYER","TRCK","TPOS","TCON"}:
            text = _decode_text(payload)
            if text:
                values[frame_id] = text
        elif frame_id == "APIC" and cover is None:
            cover = _parse_apic(payload)
    return values, cover


def _read_id3v1(path):
    try:
        with path.open("rb") as handle:
            handle.seek(-128, os.SEEK_END)
            block = handle.read(128)
    except Exception:
        return {}
    if len(block) != 128 or block[:3] != b"TAG":
        return {}
    def field(start, size):
        return block[start:start + size].decode("latin-1", errors="replace").rstrip("\x00 ").strip()
    result = {"title": field(3,30), "artist": field(33,30), "album": field(63,30), "year": _year(field(93,4))}
    if block[125] == 0 and block[126] != 0:
        result["track_no"] = int(block[126])
    return result


def _folder_fallback(path):
    for pattern in _ALBUM_FOLDER_PATTERNS:
        match = pattern.match(path.parent.name)
        if match:
            return {
                "artist": match.group("artist").strip(),
                "album": match.group("album").strip(),
                "year": int(match.group("year")),
            }
    return {}


def _external_cover(folder, cache):
    key = str(folder).casefold()
    if key in cache:
        return cache[key]
    candidates = []
    try:
        for item in folder.iterdir():
            if item.is_file() and item.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                name = item.stem.casefold()
                priority = 5 if name in {"folder","cover","front"} else 4 if "front" in name else 3 if "cover" in name or "folder" in name else 1
                candidates.append((priority, item.stat().st_size, item))
    except Exception:
        pass
    candidates.sort(reverse=True, key=lambda item: (item[0], item[1]))
    for _priority, _size, item in candidates:
        try:
            data = item.read_bytes()
            if not data or len(data) > 8 * 1024 * 1024:
                continue
            mime = {".png":"image/png", ".webp":"image/webp"}.get(item.suffix.lower(), "image/jpeg")
            cache[key] = (mime, data)
            return cache[key]
        except Exception:
            continue
    cache[key] = None
    return None


def _read_music_metadata(path, default_genre="", cover_cache=None):
    frames, cover = ({}, None)
    fallback = {}
    if path.suffix.lower() == ".mp3":
        frames, cover = _read_id3v2(path)
        fallback = _read_id3v1(path)
    folder = _folder_fallback(path)
    track_no, track_total = _split_number(frames.get("TRCK"))
    disc_no, disc_total = _split_number(frames.get("TPOS"))
    title = frames.get("TIT2") or fallback.get("title") or _LEADING_ORDER_RE.sub("", path.stem).strip() or path.stem
    artist = frames.get("TPE1") or fallback.get("artist") or folder.get("artist") or ""
    album = frames.get("TALB") or fallback.get("album") or folder.get("album") or ""
    year = _year(frames.get("TDRC") or frames.get("TYER")) or fallback.get("year") or folder.get("year")
    if cover is None:
        cover = _external_cover(path.parent, cover_cache if cover_cache is not None else {})
    return {
        "title": str(title).strip(),
        "artist": str(artist).strip(),
        "album_artist": str(frames.get("TPE2") or "").strip(),
        "album": str(album).strip(),
        "year": year,
        "track_no": track_no or fallback.get("track_no"),
        "track_total": track_total,
        "disc_no": disc_no,
        "disc_total": disc_total,
        "genre": str(frames.get("TCON") or default_genre or "").strip(),
        "duration_seconds": None,
        "cover": cover,
    }


def _upsert_cover(conn, cover):
    if not cover:
        return None
    mime, data = cover
    if not data:
        return None
    digest = hashlib.sha1(data).hexdigest()
    conn.execute(
        "INSERT OR IGNORE INTO covers(sha1, mime_type, image_data) VALUES (?, ?, ?)",
        (digest, str(mime or "image/jpeg"), sqlite3.Binary(data)),
    )
    return digest


def create_or_update_music_database(name, root_folder, default_genre=""):
    """Create/rescan one standalone non-Suno catalog under Data/MusicDB."""
    name = _safe_name(name)
    root = Path(str(root_folder or "").strip().strip('"'))
    if not root.exists() or not root.is_dir():
        raise ValueError("Mūzikas mape nav atrasta.")
    path = _db_path(name)
    conn = _connect(path)
    _ensure_schema(conn)
    info = _read_info(conn)
    now = _now_iso()
    _set_info(conn, "name", name)
    _set_info(conn, "root_folder", str(root))
    _set_info(conn, "default_genre", str(default_genre or "").strip())
    if not info.get("created_at"):
        _set_info(conn, "created_at", now)

    existing = {
        str(row["path"]).casefold(): (int(row["size_bytes"] or 0), str(row["modified_time"] or ""))
        for row in conn.execute("SELECT path, size_bytes, modified_time FROM tracks")
    }
    scanned = added = updated = unchanged = errors = 0
    error_items = []
    cover_cache = {}
    seen_paths = set()
    for current, dirnames, filenames in os.walk(str(root)):
        dirnames.sort(key=str.casefold)
        filenames.sort(key=str.casefold)
        folder = Path(current)
        for filename in filenames:
            audio_path = folder / filename
            if audio_path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
                continue
            scanned += 1
            key = str(audio_path).casefold()
            seen_paths.add(key)
            try:
                stat = audio_path.stat()
                modified = datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds")
                size = int(stat.st_size or 0)
                old = existing.get(key)
                if old == (size, modified):
                    unchanged += 1
                    continue
                meta = _read_music_metadata(audio_path, default_genre, cover_cache)
                cover_sha1 = _upsert_cover(conn, meta.get("cover"))
                params = (
                    str(audio_path), audio_path.name, meta["title"], meta["artist"], meta["album_artist"],
                    meta["album"], meta["year"], meta["track_no"], meta["track_total"], meta["disc_no"],
                    meta["disc_total"], meta["genre"], meta["duration_seconds"], audio_path.suffix.lower().lstrip("."),
                    size, modified, cover_sha1, now,
                )
                conn.execute(
                    """
                    INSERT INTO tracks(path,filename,title,artist,album_artist,album,year,track_no,track_total,
                                       disc_no,disc_total,genre,duration_seconds,format,size_bytes,modified_time,
                                       cover_sha1,imported_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(path) DO UPDATE SET
                        filename=excluded.filename,title=excluded.title,artist=excluded.artist,
                        album_artist=excluded.album_artist,album=excluded.album,year=excluded.year,
                        track_no=excluded.track_no,track_total=excluded.track_total,disc_no=excluded.disc_no,
                        disc_total=excluded.disc_total,genre=excluded.genre,duration_seconds=excluded.duration_seconds,
                        format=excluded.format,size_bytes=excluded.size_bytes,modified_time=excluded.modified_time,
                        cover_sha1=excluded.cover_sha1,imported_at=excluded.imported_at
                    """,
                    params,
                )
                if old is None:
                    added += 1
                else:
                    updated += 1
            except Exception as exc:
                errors += 1
                if len(error_items) < 20:
                    error_items.append(f"{audio_path}: {exc}")
    _set_info(conn, "last_scan_at", now)
    _set_info(conn, "last_scan_count", str(scanned))
    conn.commit()
    track_count = int(conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0] or 0)
    cover_count = int(conn.execute("SELECT COUNT(*) FROM covers").fetchone()[0] or 0)
    conn.close()
    return {
        "ok": True, "name": name, "db_path": str(path), "root_folder": str(root),
        "track_count": track_count, "cover_count": cover_count, "scanned": scanned,
        "added": added, "updated": updated, "unchanged": unchanged,
        "errors": errors, "error_items": error_items,
    }


def list_music_databases():
    MUSIC_DB_DIR.mkdir(parents=True, exist_ok=True)
    result = []
    for path in sorted(MUSIC_DB_DIR.glob("*.db"), key=lambda p: p.name.casefold()):
        try:
            conn = _connect(path)
            if not _schema_is_music_db(conn):
                conn.close()
                continue
            info = _read_info(conn)
            count = int(conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0] or 0)
            albums = int(conn.execute("SELECT COUNT(*) FROM (SELECT 1 FROM tracks GROUP BY COALESCE(NULLIF(album_artist,''),artist,''), COALESCE(album,''), COALESCE(year,0))").fetchone()[0] or 0)
            conn.close()
            result.append({
                "name": info.get("name") or path.stem,
                "file_name": path.name,
                "db_path": str(path),
                "root_folder": info.get("root_folder") or "",
                "default_genre": info.get("default_genre") or "",
                "track_count": count,
                "album_count": albums,
                "last_scan_at": info.get("last_scan_at") or "",
            })
        except Exception as exc:
            result.append({"name": path.stem, "file_name": path.name, "db_path": str(path), "error": str(exc)})
    return {"ok": True, "databases": result}


def _open_named(name):
    path = _db_path(name)
    if not path.is_file():
        raise FileNotFoundError("Mūzikas DB nav atrasta.")
    conn = _connect(path)
    if not _schema_is_music_db(conn):
        conn.close()
        raise ValueError("Fails nav LS atsevišķās mūzikas DB formātā.")
    return path, conn


def music_database_albums(name, query="", limit=1000):
    _path, conn = _open_named(name)
    query = str(query or "").strip()
    where = ""
    params = []
    if query:
        like = f"%{query}%"
        where = "WHERE artist LIKE ? COLLATE NOCASE OR album_artist LIKE ? COLLATE NOCASE OR album LIKE ? COLLATE NOCASE OR title LIKE ? COLLATE NOCASE OR CAST(year AS TEXT) LIKE ? OR genre LIKE ? COLLATE NOCASE"
        params = [like] * 6
    limit = max(1, min(int(limit or 1000), 5000))
    rows = [dict(row) for row in conn.execute(
        f"""
        SELECT COALESCE(NULLIF(TRIM(album_artist), ''), NULLIF(TRIM(artist), ''), 'Unknown Artist') AS artist,
               COALESCE(NULLIF(TRIM(album), ''), 'Singles') AS album,
               year,
               MIN(NULLIF(cover_sha1, '')) AS cover_sha1,
               COUNT(*) AS track_count,
               MIN(genre) AS genre
          FROM tracks
          {where}
         GROUP BY COALESCE(NULLIF(TRIM(album_artist), ''), NULLIF(TRIM(artist), ''), 'Unknown Artist'),
                  COALESCE(NULLIF(TRIM(album), ''), 'Singles'), year
         ORDER BY CASE WHEN year IS NULL THEN 1 ELSE 0 END, year DESC,
                  artist COLLATE NOCASE, album COLLATE NOCASE
         LIMIT ?
        """, (*params, limit)
    )]
    info = _read_info(conn)
    total_tracks = int(conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0] or 0)
    conn.close()
    return {"ok": True, "name": info.get("name") or name, "root_folder": info.get("root_folder") or "", "total_tracks": total_tracks, "albums": rows, "query": query}


def music_database_tracks(name, query="", album="", artist="", year="", limit=5000):
    _path, conn = _open_named(name)
    clauses, params = [], []
    query = str(query or "").strip()
    if query:
        like = f"%{query}%"
        clauses.append("(artist LIKE ? COLLATE NOCASE OR album_artist LIKE ? COLLATE NOCASE OR album LIKE ? COLLATE NOCASE OR title LIKE ? COLLATE NOCASE OR CAST(year AS TEXT) LIKE ? OR genre LIKE ? COLLATE NOCASE)")
        params.extend([like] * 6)
    if album:
        clauses.append("COALESCE(NULLIF(TRIM(album), ''), 'Singles') = ?")
        params.append(str(album))
    if artist:
        clauses.append("COALESCE(NULLIF(TRIM(album_artist), ''), NULLIF(TRIM(artist), ''), 'Unknown Artist') = ?")
        params.append(str(artist))
    if str(year or "").strip():
        try:
            clauses.append("year = ?")
            params.append(int(year))
        except Exception:
            pass
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    limit = max(1, min(int(limit or 5000), 10000))
    rows = [dict(row) for row in conn.execute(
        f"""
        SELECT id,title,artist,album_artist,album,year,track_no,track_total,disc_no,disc_total,
               genre,duration_seconds,format,path,cover_sha1
          FROM tracks {where}
         ORDER BY COALESCE(disc_no,0), COALESCE(track_no,999999), title COLLATE NOCASE
         LIMIT ?
        """, (*params, limit)
    )]
    info = _read_info(conn)
    conn.close()
    return {"ok": True, "name": info.get("name") or name, "rows": rows, "query": query}


def get_music_database_cover(name, sha1_value):
    _path, conn = _open_named(name)
    digest = str(sha1_value or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", digest):
        conn.close()
        return None
    row = conn.execute("SELECT mime_type,image_data FROM covers WHERE sha1=? LIMIT 1", (digest,)).fetchone()
    conn.close()
    if not row:
        return None
    return {"mime_type": str(row["mime_type"] or "image/jpeg"), "image_data": bytes(row["image_data"] or b"")}