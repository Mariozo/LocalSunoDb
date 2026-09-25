"""Standalone local music-library databases for non-Suno collections.

This module deliberately keeps "home music" catalogs separate from the canonical
Suno/LocalSunoDb database.  It never moves, renames, edits, or deletes audio files.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import struct
import unicodedata
from datetime import datetime
from pathlib import Path

from ls_core.runtime import DATA_DIR


MUSIC_DB_DIR = DATA_DIR / "MusicDB"
SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".m4a", ".aac", ".ogg"}

_ALBUM_FOLDER_RE = re.compile(
    r"^\s*\[(?P<year>\d{4})\]\s*-\s*(?P<artist>.+?)\s*-\s*(?P<album>.+?)\s*$"
)
_LEADING_FILE_ORDER_RE = re.compile(
    r"^\s*(?:[\(\[]\s*)?\d{1,4}(?:\s*[\)\]])?\s*[-._]\s*"
)
_YEAR_RE = re.compile(r"(?<!\d)(18|19|20|21)\d{2}(?!\d)")


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_db_slug(value):
    text = unicodedata.normalize("NFKC", str(value or "")).strip()
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    if not text:
        raise ValueError("DB nosaukums nevar būt tukšs.")
    return text[:80]


def _db_path(name):
    slug = _safe_db_slug(name)
    MUSIC_DB_DIR.mkdir(parents=True, exist_ok=True)
    return MUSIC_DB_DIR / f"{slug}.db"


def _connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


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


def _syncsafe(value):
    if len(value) != 4:
        return 0
    return (
        ((value[0] & 0x7F) << 21)
        | ((value[1] & 0x7F) << 14)
        | ((value[2] & 0x7F) << 7)
        | (value[3] & 0x7F)
    )


def _decode_text_payload(payload):
    if not payload:
        return ""
    encoding = payload[0]
    data = payload[1:]
    try:
        if encoding == 0:
            text = data.decode("latin-1", errors="replace")
        elif encoding == 1:
            text = data.decode("utf-16", errors="replace")
        elif encoding == 2:
            text = data.decode("utf-16-be", errors="replace")
        else:
            text = data.decode("utf-8", errors="replace")
    except Exception:
        text = data.decode("utf-8", errors="replace")
    return text.replace("\x00", " / ").strip(" \t\r\n/")


def _split_number_pair(value):
    text = str(value or "").strip()
    if not text:
        return None, None
    parts = text.split("/", 1)
    try:
        current = int(re.sub(r"\D.*$", "", parts[0]).strip())
    except Exception:
        current = None
    total = None
    if len(parts) > 1:
        try:
            total = int(re.sub(r"\D.*$", "", parts[1]).strip())
        except Exception:
            total = None
    return current, total


def _year_value(value):
    match = _YEAR_RE.search(str(value or ""))
    return int(match.group(0)) if match else None


def _skip_encoded_terminated(data, start, encoding):
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
    desc_start = mime_end + 2  # picture type byte follows MIME terminator
    image_start = _skip_encoded_terminated(payload, desc_start, encoding)
    image = payload[image_start:]
    if not image:
        return None
    return mime, image


def _read_id3v2(path):
    result = {}
    cover = None
    try:
        with path.open("rb") as handle:
            header = handle.read(10)
            if len(header) != 10 or header[:3] != b"ID3":
                return result, cover
            version = header[3]
            tag_size = _syncsafe(header[6:10])
            data = handle.read(tag_size)
    except Exception:
        return result, cover

    pos = 0
    while pos < len(data):
        if version == 2:
            if pos + 6 > len(data):
                break
            frame_id = data[pos:pos + 3].decode("latin-1", errors="ignore")
            size = int.from_bytes(data[pos + 3:pos + 6], "big")
            header_size = 6
            mapped = {
                "TT2": "TIT2", "TP1": "TPE1", "TP2": "TPE2",
                "TAL": "TALB", "TYE": "TYER", "TRK": "TRCK",
                "TPA": "TPOS", "TCO": "TCON",
            }.get(frame_id, frame_id)
            frame_id = mapped
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
        start = pos + header_size
        end = start + size
        if end > len(data):
            break
        payload = data[start:end]
        pos = end

        if frame_id in {"TIT2", "TPE1", "TPE2", "TALB", "TDRC", "TYER", "TRCK", "TPOS", "TCON"}:
            value = _decode_text_payload(payload)
            if value:
                result[frame_id] = value
        elif frame_id == "APIC" and cover is None:
            cover = _parse_apic(payload)
        elif version == 2 and frame_id == "PIC" and cover is None:
            # ID3v2.2 PIC: encoding, 3-byte format, type, description, image.
            if len(payload) >= 6:
                encoding = payload[0]
                fmt = payload[1:4].decode("latin-1", errors="ignore").upper()
                mime = "image/png" if fmt == "PNG" else "image/jpeg"
                image_start = _skip_encoded_terminated(payload, 5, encoding)
                image = payload[image_start:]
                if image:
                    cover = (mime, image)

    return result, cover


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

    result = {
        "title": field(3, 30),
        "artist": field(33, 30),
        "album": field(63, 30),
        "year": _year_value(field(93, 4)),
    }
    if block[125] == 0 and block[126] != 0:
        result["track_no"] = int(block[126])
    return result


def _read_mp3_metadata(path):
    frames, cover = _read_id3v2(path)
    fallback = _read_id3v1(path)
    track_no, track_total = _split_number_pair(frames.get("TRCK"))
    disc_no, disc_total = _split_number_pair(frames.get("TPOS"))
    return {
        "title": frames.get("TIT2") or fallback.get("title") or "",
        "artist": frames.get("TPE1") or fallback.get("artist") or "",
        "album_artist": frames.get("TPE2") or "",
        "album": frames.get("TALB") or fallback.get("album") or "",
        "year": _year_value(frames.get("TDRC") or frames.get("TYER")) or fallback.get("year"),
        "track_no": track_no or fallback.get("track_no"),
        "track_total": track_total,
        "disc_no": disc_no,
        "disc_total": disc_total,
        "genre": frames.get("TCON") or "",
        "duration_seconds": None,
        "cover": cover,
    }


def _read_flac_metadata(path):
    result = {
        "title": "", "artist": "", "album_artist": "", "album": "",
        "year": None, "track_no": None, "track_total": None,
        "disc_no": None, "disc_total": None, "genre": "",
        "duration_seconds": None, "cover": None,
    }
    comments = {}
    try:
        with path.open("rb") as handle:
            if handle.read(4) != b"fLaC":
                return result
            last = False
            while not last:
                header = handle.read(4)
                if len(header) != 4:
                    break
                last = bool(header[0] & 0x80)
                block_type = header[0] & 0x7F
                length = int.from_bytes(header[1:4], "big")
                data = handle.read(length)
                if len(data) != length:
                    break

                if block_type == 0 and len(data) >= 18:
                    packed = int.from_bytes(data[10:18], "big")
                    sample_rate = (packed >> 44) & 0xFFFFF
                    total_samples = packed & 0xFFFFFFFFF
                    if sample_rate:
                        result["duration_seconds"] = total_samples / sample_rate
                elif block_type == 4:
                    pos = 0
                    if len(data) < 8:
                        continue
                    vendor_len = int.from_bytes(data[pos:pos + 4], "little")
                    pos += 4 + vendor_len
                    if pos + 4 > len(data):
                        continue
                    count = int.from_bytes(data[pos:pos + 4], "little")
                    pos += 4
                    for _ in range(count):
                        if pos + 4 > len(data):
                            break
                        item_len = int.from_bytes(data[pos:pos + 4], "little")
                        pos += 4
                        item = data[pos:pos + item_len]
                        pos += item_len
                        text = item.decode("utf-8", errors="replace")
                        if "=" in text:
                            key, value = text.split("=", 1)
                            comments.setdefault(key.upper(), value.strip())
                elif block_type == 6 and result["cover"] is None:
                    pos = 0
                    if len(data) < 32:
                        continue
                    pos += 4  # picture type
                    mime_len = int.from_bytes(data[pos:pos + 4], "big")
                    pos += 4
                    mime = data[pos:pos + mime_len].decode("ascii", errors="replace") or "image/jpeg"
                    pos += mime_len
                    desc_len = int.from_bytes(data[pos:pos + 4], "big")
                    pos += 4 + desc_len
                    if pos + 20 > len(data):
                        continue
                    pos += 16  # width, height, depth, indexed colors
                    image_len = int.from_bytes(data[pos:pos + 4], "big")
                    pos += 4
                    image = data[pos:pos + image_len]
                    if image:
                        result["cover"] = (mime, image)
    except Exception:
        return result

    track_no, track_total = _split_number_pair(
        comments.get("TRACKNUMBER") or ""
    )
    if not track_total:
        _, track_total = _split_number_pair(
            f"/{comments.get('TRACKTOTAL') or comments.get('TOTALTRACKS') or ''}"
        )
    disc_no, disc_total = _split_number_pair(comments.get("DISCNUMBER") or "")
    if not disc_total:
        _, disc_total = _split_number_pair(
            f"/{comments.get('DISCTOTAL') or comments.get('TOTALDISCS') or ''}"
        )

    result.update({
        "title": comments.get("TITLE", ""),
        "artist": comments.get("ARTIST", ""),
        "album_artist": comments.get("ALBUMARTIST", ""),
        "album": comments.get("ALBUM", ""),
        "year": _year_value(comments.get("DATE") or comments.get("YEAR")),
        "track_no": track_no,
        "track_total": track_total,
        "disc_no": disc_no,
        "disc_total": disc_total,
        "genre": comments.get("GENRE", ""),
    })
    return result


def _external_cover_for_folder(folder, cache):
    key = str(folder).casefold()
    if key in cache:
        return cache[key]

    best = None
    try:
        files = [
            item for item in folder.iterdir()
            if item.is_file() and item.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        ]
    except Exception:
        files = []

    def score(item):
        name = item.stem.casefold()
        preferred = 0
        if name in {"folder", "cover", "front"}:
            preferred = 5
        elif "front" in name:
            preferred = 4
        elif "cover" in name or "folder" in name:
            preferred = 3
        elif "albumart" in name and "small" not in name:
            preferred = 2
        elif "albumart" in name:
            preferred = 1
        try:
            size = item.stat().st_size
        except Exception:
            size = 0
        return preferred, size

    if files:
        files.sort(key=score, reverse=True)
        best = files[0]
        try:
            data = best.read_bytes()
            if len(data) > 8 * 1024 * 1024:
                best = None
            else:
                mime = {
                    ".png": "image/png",
                    ".webp": "image/webp",
                }.get(best.suffix.lower(), "image/jpeg")
                cache[key] = (mime, data)
                return cache[key]
        except Exception:
            best = None

    cache[key] = None
    return None


def _clean_fallback_title(path):
    title = _LEADING_FILE_ORDER_RE.sub("", path.stem).strip()
    return title or path.stem


def _folder_fallback(path):
    parent = path.parent
    match = _ALBUM_FOLDER_RE.match(parent.name)
    if match:
        return {
            "artist": match.group("artist").strip(),
            "album": match.group("album").strip(),
            "year": int(match.group("year")),
        }
    return {}


def read_music_file_metadata(path, default_genre="", folder_cover_cache=None):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".mp3":
        meta = _read_mp3_metadata(path)
    elif suffix == ".flac":
        meta = _read_flac_metadata(path)
    else:
        meta = {
            "title": "", "artist": "", "album_artist": "", "album": "",
            "year": None, "track_no": None, "track_total": None,
            "disc_no": None, "disc_total": None, "genre": "",
            "duration_seconds": None, "cover": None,
        }

    folder = _folder_fallback(path)
    meta["title"] = str(meta.get("title") or _clean_fallback_title(path)).strip()
    meta["artist"] = str(meta.get("artist") or folder.get("artist") or "").strip()
    meta["album"] = str(meta.get("album") or folder.get("album") or "").strip()
    meta["year"] = meta.get("year") or folder.get("year")
    meta["genre"] = str(meta.get("genre") or default_genre or "").strip()

    cover = meta.get("cover")
    if cover is None:
        cover = _external_cover_for_folder(
            path.parent,
            folder_cover_cache if folder_cover_cache is not None else {},
        )
    meta["cover"] = cover
    return meta


def _upsert_cover(conn, cover):
    if not cover:
        return None
    mime, data = cover
    if not data:
        return None
    digest = hashlib.sha1(data).hexdigest()
    conn.execute(
        "INSERT OR IGNORE INTO covers(sha1, mime_type, image_data) VALUES (?, ?, ?)",
        (digest, str(mime or ""), sqlite3.Binary(data)),
    )
    return digest


def create_or_update_music_database(name, root_folder, default_genre=""):
    name = _safe_db_slug(name)
    root = Path(str(root_folder or "").strip().strip('"'))
    if not root.exists() or not root.is_dir():
        raise ValueError("Mūzikas mape nav atrasta.")

    path = _db_path(name)
    conn = _connect(path)
    _ensure_schema(conn)
    now = _now_iso()
    _set_info(conn, "name", name)
    _set_info(conn, "root_folder", str(root))
    _set_info(conn, "default_genre", str(default_genre or "").strip())
    if not _read_info(conn).get("created_at"):
        _set_info(conn, "created_at", now)

    existing = {
        str(row["path"]).casefold(): (int(row["size_bytes"] or 0), str(row["modified_time"] or ""))
        for row in conn.execute("SELECT path, size_bytes, modified_time FROM tracks")
    }
    cover_cache = {}
    scanned = added = updated = unchanged = errors = 0
    error_items = []

    for current_folder, dirnames, filenames in os.walk(str(root)):
        dirnames.sort(key=lambda value: value.casefold())
        filenames.sort(key=lambda value: value.casefold())
        folder = Path(current_folder)
        for filename in filenames:
            audio_path = folder / filename
            if audio_path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
                continue
            scanned += 1
            try:
                stat = audio_path.stat()
                modified = datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds")
                size = int(stat.st_size or 0)
                key = str(audio_path).casefold()
                old = existing.get(key)
                if old == (size, modified):
                    unchanged += 1
                    continue

                meta = read_music_file_metadata(
                    audio_path,
                    default_genre=default_genre,
                    folder_cover_cache=cover_cache,
                )
                cover_sha1 = _upsert_cover(conn, meta.get("cover"))
                params = (
                    str(audio_path),
                    audio_path.name,
                    meta.get("title") or "",
                    meta.get("artist") or "",
                    meta.get("album_artist") or "",
                    meta.get("album") or "",
                    meta.get("year"),
                    meta.get("track_no"),
                    meta.get("track_total"),
                    meta.get("disc_no"),
                    meta.get("disc_total"),
                    meta.get("genre") or "",
                    meta.get("duration_seconds"),
                    audio_path.suffix.lower().lstrip("."),
                    size,
                    modified,
                    cover_sha1,
                    now,
                )
                was_existing = key in existing
                conn.execute(
                    """
                    INSERT INTO tracks(
                        path, filename, title, artist, album_artist, album, year,
                        track_no, track_total, disc_no, disc_total, genre,
                        duration_seconds, format, size_bytes, modified_time,
                        cover_sha1, imported_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(path) DO UPDATE SET
                        filename=excluded.filename,
                        title=excluded.title,
                        artist=excluded.artist,
                        album_artist=excluded.album_artist,
                        album=excluded.album,
                        year=excluded.year,
                        track_no=excluded.track_no,
                        track_total=excluded.track_total,
                        disc_no=excluded.disc_no,
                        disc_total=excluded.disc_total,
                        genre=excluded.genre,
                        duration_seconds=excluded.duration_seconds,
                        format=excluded.format,
                        size_bytes=excluded.size_bytes,
                        modified_time=excluded.modified_time,
                        cover_sha1=excluded.cover_sha1,
                        imported_at=excluded.imported_at
                    """,
                    params,
                )
                if was_existing:
                    updated += 1
                else:
                    added += 1
                existing[key] = (size, modified)
            except Exception as exc:
                errors += 1
                if len(error_items) < 20:
                    error_items.append(f"{audio_path}: {exc}")

    _set_info(conn, "last_scan_at", now)
    _set_info(conn, "last_scan_count", scanned)
    conn.commit()
    total = int(conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0] or 0)
    cover_count = int(conn.execute("SELECT COUNT(*) FROM covers").fetchone()[0] or 0)
    conn.close()

    return {
        "ok": True,
        "name": name,
        "db_path": str(path),
        "root_folder": str(root),
        "default_genre": str(default_genre or "").strip(),
        "scanned": scanned,
        "added": added,
        "updated": updated,
        "unchanged": unchanged,
        "errors": errors,
        "error_items": error_items,
        "track_count": total,
        "cover_count": cover_count,
    }


def list_music_databases():
    MUSIC_DB_DIR.mkdir(parents=True, exist_ok=True)
    result = []
    for path in sorted(MUSIC_DB_DIR.glob("*.db"), key=lambda item: item.name.casefold()):
        try:
            conn = _connect(path)
            _ensure_schema(conn)
            info = _read_info(conn)
            count = int(conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0] or 0)
            artists = int(
                conn.execute(
                    "SELECT COUNT(DISTINCT artist) FROM tracks WHERE TRIM(artist) != ''"
                ).fetchone()[0] or 0
            )
            covers = int(conn.execute("SELECT COUNT(*) FROM covers").fetchone()[0] or 0)
            conn.close()
            result.append({
                "name": info.get("name") or path.stem,
                "db_file": path.name,
                "db_path": str(path),
                "root_folder": info.get("root_folder") or "",
                "default_genre": info.get("default_genre") or "",
                "track_count": count,
                "artist_count": artists,
                "cover_count": covers,
                "last_scan_at": info.get("last_scan_at") or "",
            })
        except Exception as exc:
            result.append({
                "name": path.stem,
                "db_file": path.name,
                "db_path": str(path),
                "error": str(exc),
            })
    return {"ok": True, "databases": result}


def search_music_database(name, query="", limit=300):
    path = _db_path(name)
    if not path.is_file():
        raise FileNotFoundError("Mūzikas DB nav atrasta.")

    limit = max(1, min(1000, int(limit or 300)))
    query = str(query or "").strip()
    conn = _connect(path)
    _ensure_schema(conn)

    params = []
    where = ""
    if query:
        like = f"%{query}%"
        where = """
         WHERE title LIKE ? COLLATE NOCASE
            OR artist LIKE ? COLLATE NOCASE
            OR album_artist LIKE ? COLLATE NOCASE
            OR album LIKE ? COLLATE NOCASE
            OR CAST(year AS TEXT) LIKE ?
            OR genre LIKE ? COLLATE NOCASE
        """
        params = [like, like, like, like, like, like]

    rows = [
        dict(row)
        for row in conn.execute(
            f"""
            SELECT id, title, artist, album_artist, album, year,
                   track_no, track_total, disc_no, disc_total, genre,
                   format, path, duration_seconds, cover_sha1
              FROM tracks
              {where}
             ORDER BY
                   CASE WHEN TRIM(artist)='' THEN 1 ELSE 0 END,
                   artist COLLATE NOCASE,
                   CASE WHEN year IS NULL THEN 1 ELSE 0 END,
                   year,
                   album COLLATE NOCASE,
                   COALESCE(disc_no, 0),
                   COALESCE(track_no, 999999),
                   title COLLATE NOCASE
             LIMIT ?
            """,
            (*params, limit),
        )
    ]
    info = _read_info(conn)
    total = int(conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0] or 0)
    conn.close()
    return {
        "ok": True,
        "name": info.get("name") or path.stem,
        "db_path": str(path),
        "root_folder": info.get("root_folder") or "",
        "default_genre": info.get("default_genre") or "",
        "query": query,
        "total": total,
        "shown": len(rows),
        "rows": rows,
    }


def get_music_database_cover(name, sha1_value):
    path = _db_path(name)
    if not path.is_file():
        return None
    sha1_value = str(sha1_value or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", sha1_value):
        return None
    conn = _connect(path)
    _ensure_schema(conn)
    row = conn.execute(
        "SELECT mime_type, image_data FROM covers WHERE sha1=? LIMIT 1",
        (sha1_value,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "mime_type": str(row["mime_type"] or "image/jpeg"),
        "image_data": bytes(row["image_data"] or b""),
    }


def music_database_preview(name, limit=40):
    path = _db_path(name)
    if not path.is_file():
        raise FileNotFoundError("Mūzikas DB nav atrasta.")
    limit = max(1, min(200, int(limit or 40)))
    conn = _connect(path)
    _ensure_schema(conn)
    rows = [
        dict(row)
        for row in conn.execute(
            """
            SELECT title, artist, album, year, track_no, disc_no, genre, format, path,
                   CASE WHEN cover_sha1 IS NULL OR cover_sha1='' THEN 0 ELSE 1 END AS has_cover
              FROM tracks
             ORDER BY
                   CASE WHEN TRIM(artist)='' THEN 1 ELSE 0 END,
                   artist COLLATE NOCASE,
                   CASE WHEN year IS NULL THEN 1 ELSE 0 END,
                   year,
                   album COLLATE NOCASE,
                   COALESCE(disc_no, 0),
                   COALESCE(track_no, 999999),
                   title COLLATE NOCASE
             LIMIT ?
            """,
            (limit,),
        )
    ]
    info = _read_info(conn)
    conn.close()
    return {
        "ok": True,
        "name": info.get("name") or path.stem,
        "rows": rows,
    }
