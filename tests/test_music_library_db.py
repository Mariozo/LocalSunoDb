import sqlite3
from pathlib import Path

import pytest

from ls_data import music_library


def syncsafe(value):
    return bytes([
        (value >> 21) & 0x7F,
        (value >> 14) & 0x7F,
        (value >> 7) & 0x7F,
        value & 0x7F,
    ])


def id3_text_frame(frame_id, value):
    payload = b"\x03" + value.encode("utf-8")
    return frame_id.encode("ascii") + len(payload).to_bytes(4, "big") + b"\x00\x00" + payload


def id3_apic_frame(image):
    payload = b"\x00image/jpeg\x00\x03\x00" + image
    return b"APIC" + len(payload).to_bytes(4, "big") + b"\x00\x00" + payload


def write_tagged_mp3(path, *, title, artist, album, year, track, genre, image):
    frames = b"".join([
        id3_text_frame("TIT2", title),
        id3_text_frame("TPE1", artist),
        id3_text_frame("TPE2", artist),
        id3_text_frame("TALB", album),
        id3_text_frame("TDRC", str(year)),
        id3_text_frame("TRCK", track),
        id3_text_frame("TPOS", "1/1"),
        id3_text_frame("TCON", genre),
        id3_apic_frame(image),
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"ID3\x03\x00\x00" + syncsafe(len(frames)) + frames + b"\xff\xfb\x90\x64" + b"\x00" * 64)


def flac_block(block_type, data, *, last=False):
    first = block_type | (0x80 if last else 0)
    return bytes([first]) + len(data).to_bytes(3, "big") + data


def write_tagged_flac(path, *, title, artist, album, year, track, genre, image):
    sample_rate = 44100
    total_samples = sample_rate * 120
    packed = (sample_rate << 44) | (1 << 41) | (15 << 36) | total_samples
    streaminfo = bytearray(34)
    streaminfo[10:18] = packed.to_bytes(8, "big")

    vendor = b"LocalSunoDb test"
    comments = [
        f"TITLE={title}",
        f"ARTIST={artist}",
        f"ALBUMARTIST={artist}",
        f"ALBUM={album}",
        f"DATE={year}",
        f"TRACKNUMBER={track}",
        "TRACKTOTAL=9",
        "DISCNUMBER=1",
        "DISCTOTAL=1",
        f"GENRE={genre}",
    ]
    vorbis = len(vendor).to_bytes(4, "little") + vendor + len(comments).to_bytes(4, "little")
    for item in comments:
        raw = item.encode("utf-8")
        vorbis += len(raw).to_bytes(4, "little") + raw

    mime = b"image/png"
    picture = (
        (3).to_bytes(4, "big")
        + len(mime).to_bytes(4, "big") + mime
        + (0).to_bytes(4, "big")
        + (600).to_bytes(4, "big")
        + (600).to_bytes(4, "big")
        + (24).to_bytes(4, "big")
        + (0).to_bytes(4, "big")
        + len(image).to_bytes(4, "big") + image
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"fLaC"
        + flac_block(0, bytes(streaminfo))
        + flac_block(4, vorbis)
        + flac_block(6, picture, last=True)
    )


@pytest.fixture()
def isolated_music_db(tmp_path, monkeypatch):
    db_dir = tmp_path / "MusicDB"
    monkeypatch.setattr(music_library, "MUSIC_DB_DIR", db_dir)
    return db_dir


def test_reads_mp3_and_flac_metadata_and_deduplicates_covers(isolated_music_db, tmp_path):
    root = tmp_path / "Jazz"
    cover = b"\xff\xd8\xff\xe0" + b"album-cover" * 12
    write_tagged_mp3(
        root / "(01) - Al Jarreau - Spirit.mp3",
        title="Spirit",
        artist="Al Jarreau",
        album="We Got By",
        year=1975,
        track="1/9",
        genre="Jazz",
        image=cover,
    )
    write_tagged_mp3(
        root / "(02) - Al Jarreau - We Got By.mp3",
        title="We Got By",
        artist="Al Jarreau",
        album="We Got By",
        year=1975,
        track="2/9",
        genre="Jazz",
        image=cover,
    )
    flac_cover = b"\x89PNG\r\n\x1a\n" + b"flac-cover" * 10
    write_tagged_flac(
        root / "Brad Mehldau" / "01 - Song.flac",
        title="Song",
        artist="Brad Mehldau",
        album="Test Album",
        year=2002,
        track="1/9",
        genre="Jazz",
        image=flac_cover,
    )

    result = music_library.create_or_update_music_database("Jazz", root, "Jazz")

    assert result["ok"] is True
    assert result["track_count"] == 3
    assert result["added"] == 3
    assert result["cover_count"] == 2

    conn = sqlite3.connect(isolated_music_db / "Jazz.db")
    conn.row_factory = sqlite3.Row
    try:
        spirit = conn.execute(
            "SELECT * FROM tracks WHERE title='Spirit'"
        ).fetchone()
        flac = conn.execute(
            "SELECT * FROM tracks WHERE artist='Brad Mehldau'"
        ).fetchone()
        cover_count = conn.execute("SELECT COUNT(*) FROM covers").fetchone()[0]
    finally:
        conn.close()

    assert spirit["artist"] == "Al Jarreau"
    assert spirit["album"] == "We Got By"
    assert spirit["year"] == 1975
    assert spirit["track_no"] == 1
    assert spirit["track_total"] == 9
    assert spirit["genre"] == "Jazz"
    assert spirit["cover_sha1"]

    assert flac["album"] == "Test Album"
    assert flac["year"] == 2002
    assert flac["track_no"] == 1
    assert flac["track_total"] == 9
    assert flac["disc_no"] == 1
    assert 119.9 < flac["duration_seconds"] < 120.1
    assert flac["cover_sha1"]
    assert cover_count == 2

    search_1975 = music_library.search_music_database("Jazz", "1975")
    assert search_1975["shown"] == 2
    assert {row["title"] for row in search_1975["rows"]} == {"Spirit", "We Got By"}

    search_artist = music_library.search_music_database("Jazz", "Brad Mehldau")
    assert search_artist["shown"] == 1
    assert search_artist["rows"][0]["album"] == "Test Album"

    cover_payload = music_library.get_music_database_cover(
        "Jazz",
        spirit["cover_sha1"],
    )
    assert cover_payload is not None
    assert cover_payload["mime_type"] == "image/jpeg"
    assert cover_payload["image_data"] == cover

    second = music_library.create_or_update_music_database("Jazz", root, "Jazz")
    assert second["added"] == 0
    assert second["updated"] == 0
    assert second["unchanged"] == 3


def test_folder_fallback_cleans_file_order_and_uses_album_art(isolated_music_db, tmp_path):
    album = tmp_path / "Jazz" / "[1975] - Al Jarreau - We Got By"
    album.mkdir(parents=True)
    (album / "(01) - Al Jarreau - Spirit.wav").write_bytes(b"RIFF-test")
    (album / "Folder.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"folder-cover" * 20)

    result = music_library.create_or_update_music_database("Jazz Home", tmp_path / "Jazz", "Jazz")
    assert result["track_count"] == 1
    assert result["cover_count"] == 1

    conn = sqlite3.connect(isolated_music_db / "Jazz Home.db")
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM tracks").fetchone()
    finally:
        conn.close()

    assert row["title"] == "Al Jarreau - Spirit"
    assert row["artist"] == "Al Jarreau"
    assert row["album"] == "We Got By"
    assert row["year"] == 1975
    assert row["track_no"] is None
    assert row["genre"] == "Jazz"
    assert row["cover_sha1"]


def test_multiple_named_databases_are_kept_separate(isolated_music_db, tmp_path):
    jazz = tmp_path / "Jazz"
    classical = tmp_path / "Classical"
    jazz.mkdir()
    classical.mkdir()
    (jazz / "Jazz Song.wav").write_bytes(b"RIFF-jazz")
    (classical / "Classical Song.wav").write_bytes(b"RIFF-classical")

    music_library.create_or_update_music_database("Jazz", jazz, "Jazz")
    music_library.create_or_update_music_database("Classical", classical, "Classical")

    payload = music_library.list_music_databases()
    assert payload["ok"] is True
    assert [item["name"] for item in payload["databases"]] == ["Classical", "Jazz"]
    assert {item["track_count"] for item in payload["databases"]} == {1}

    jazz_preview = music_library.music_database_preview("Jazz")
    classical_preview = music_library.music_database_preview("Classical")
    assert jazz_preview["rows"][0]["title"] == "Jazz Song"
    assert classical_preview["rows"][0]["title"] == "Classical Song"
