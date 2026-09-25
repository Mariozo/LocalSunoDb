import json
import sqlite3
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ls_data.local_suno_migration import create_schema

DATA_DIR = ROOT / "Data"
DB_PATH = DATA_DIR / "local_suno.db"
TEMP_DIR = ROOT / "Temp" / "direct-canonical"
SETTINGS_PATH = DATA_DIR / "localsunodb_settings.json"
REGISTRY_PATH = DATA_DIR / "ls_database_registry.json"


def write_wav(path, seconds=0.12):
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = max(1, int(48000 * seconds))
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(48000)
        wav_file.writeframes(b"\x00\x00\x00\x00" * frames)


def add_track(
    conn,
    *,
    track_id,
    title,
    created_at,
    workspace,
    source_task,
    kind,
    duration,
    bpm,
    liked=0,
    style="",
    tags="",
    marks=0,
    rating=0,
    manual_category="",
    local_path="",
    with_stem=False,
):
    conn.execute(
        """
        INSERT INTO tracks(
            id,title,created_at,workspace_id,workspace_name,audio_url,
            image_url,image_large_url,model_name,major_model_version,
            source_type,source_task,style_tags,prompt,duration_seconds,
            avg_bpm,is_liked,display_tags,kind,lyrics,library_status,
            finder_hidden
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)
        """,
        (
            track_id,
            title,
            created_at,
            "ws-" + workspace.lower().replace(" ", "-"),
            workspace,
            "https://example.invalid/" + track_id + ".mp3",
            "",
            "",
            "chirp-test",
            "v5.5",
            "gen",
            source_task,
            style,
            "Prompt for " + title,
            duration,
            bpm,
            liked,
            style,
            kind,
            "Lyrics for " + title,
            "active",
        ),
    )
    conn.execute(
        """
        INSERT INTO track_user(track_id,rating,tags,marks,manual_category,updated_at)
        VALUES (?,?,?,?,?,'2026-09-25T10:00:00Z')
        """,
        (track_id, rating, tags, marks, manual_category),
    )

    if local_path:
        variant_id = conn.execute(
            """
            INSERT INTO track_variants(track_id,variant_no,label,folder_path,variant_kind)
            VALUES (?,1,'1',?,'main')
            """,
            (track_id, str(Path(local_path).parent)),
        ).lastrowid
        conn.execute(
            """
            INSERT INTO media_files(
                variant_id,path,role,format,stem_label,size_bytes,modified_at,
                file_created_at,file_created_at_source,chronology_at
            ) VALUES (?,?,'main','wav','',4,'2026-09-25T10:00:00Z',
                      '2026-09-25T10:00:00Z','modified_time','2026-09-25T10:00:00Z')
            """,
            (variant_id, local_path),
        )
        if with_stem:
            stem_path = str(Path(local_path).with_name(Path(local_path).stem + " (Vocals).wav"))
            write_wav(Path(stem_path))
            conn.execute(
                """
                INSERT INTO media_files(
                    variant_id,path,role,format,stem_label,size_bytes,modified_at,
                    file_created_at,file_created_at_source,chronology_at
                ) VALUES (?,?,'stem','wav','Vocals',4,'2026-09-25T10:00:00Z',
                          '2026-09-25T10:00:00Z','modified_time','2026-09-25T10:00:00Z')
                """,
                (variant_id, stem_path),
            )


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    for path in (DB_PATH, SETTINGS_PATH, REGISTRY_PATH):
        if path.exists():
            path.unlink()

    conn = sqlite3.connect(DB_PATH)
    create_schema(conn)

    alpha_audio = TEMP_DIR / "Alpha Cover.wav"
    write_wav(alpha_audio)
    add_track(
        conn,
        track_id="cutover-alpha",
        title="Alpha Cover",
        created_at="2026-09-25T12:00:00Z",
        workspace="Studio A",
        source_task="Cover",
        kind="Song",
        duration=120.0,
        bpm=110.0,
        liked=1,
        style="jazz bright",
        tags="#fav, #mix",
        marks=1,
        rating=5,
        local_path=str(alpha_audio),
        with_stem=True,
    )
    add_track(
        conn,
        track_id="cutover-beta",
        title="Beta Instrumental",
        created_at="2026-09-25T11:00:00Z",
        workspace="Studio A",
        source_task="Extend",
        kind="Instrumental",
        duration=90.0,
        bpm=95.0,
        style="ambient",
        tags="#mix",
        marks=3,
        rating=3,
        manual_category="Song",
    )
    add_track(
        conn,
        track_id="cutover-gamma",
        title="Gamma Song",
        created_at="2026-09-25T10:00:00Z",
        workspace="Studio B",
        source_task="Cover",
        kind="Instrumental",
        duration=180.0,
        bpm=128.0,
        style="rock",
        tags="#rock",
        marks=5,
        rating=4,
    )

    # Enough canonical rows to force Library cursor/lazy loading.
    for index in range(4, 76):
        add_track(
            conn,
            track_id=f"cutover-{index:03d}",
            title=f"Lazy Track {index:03d}",
            created_at=f"2026-09-24T{(index % 20):02d}:{(index % 60):02d}:00Z",
            workspace="Bulk A" if index % 2 == 0 else "Bulk B",
            source_task="Create",
            kind="Song" if index % 3 else "Instrumental",
            duration=60.0 + index,
            bpm=80.0 + (index % 50),
            liked=1 if index % 10 == 0 else 0,
            style="bulk",
            tags="#bulk" if index % 5 == 0 else "",
            marks=1 if index % 7 == 0 else 0,
            rating=index % 6,
        )

    conn.commit()
    conn.close()

    SETTINGS_PATH.write_text(
        json.dumps(
            {
                "initial_setup_complete": True,
                "saved_views": [],
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
