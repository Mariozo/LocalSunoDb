import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ls_data import local_suno_migration as migration
DATA_DIR = ROOT / "Data"
DB_PATH = DATA_DIR / "local_suno.db"
PLAYLISTS_PATH = DATA_DIR / "localsunodb_playlists.json"
TEMP_DIR = ROOT / "Temp"


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    migration.create_schema(conn)

    for index, title in enumerate(("Browser Track One", "Browser Track Two", "Browser Track Three"), start=1):
        track_id = f"browser-{index}"
        wav_path = TEMP_DIR / f"{track_id}.wav"
        wav_path.write_bytes(b"RIFFbrowser-test")

        conn.execute(
            """
            INSERT INTO tracks(
                id,title,created_at,workspace_id,workspace_name,audio_url,
                model_name,major_model_version,source_type,source_task,
                style_tags,prompt,duration_seconds,avg_bpm,is_liked,
                display_tags,kind,lyrics,library_status
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                track_id,
                title,
                f"2026-09-24T10:0{index}:00Z",
                "browser-workspace",
                "Browser",
                f"https://example.invalid/{track_id}.mp3",
                "browser-model",
                "v5.5",
                "gen",
                "cover",
                "browser",
                "browser prompt",
                180.0 + index,
                120.0,
                0,
                "browser",
                "Instrumental",
                "",
                "active",
            ),
        )
        conn.execute(
            """
            INSERT INTO track_user(track_id,rating,tags,marks,manual_category,updated_at)
            VALUES (?,?,?,?,?,?)
            """,
            (track_id, 0, "", 0, "Instrumental", "2026-09-24T10:00:00Z"),
        )
        cur = conn.execute(
            """
            INSERT INTO track_variants(track_id,variant_no,label,folder_path,variant_kind)
            VALUES (?,?,?,?,?)
            """,
            (track_id, 1, "1", str(TEMP_DIR), "main"),
        )
        conn.execute(
            """
            INSERT INTO media_files(
                variant_id,path,role,format,stem_label,size_bytes,modified_at,
                file_created_at_source,chronology_at
            ) VALUES (?,?,'main','wav','',1,'2026-09-24T10:00:00Z',
                      'modified_time','2026-09-24T10:00:00Z')
            """,
            (cur.lastrowid, str(wav_path)),
        )

    conn.commit()
    conn.close()

    payload = {
        "schema_version": 1,
        "playlists": [
            {
                "id": "playlist-name-day",
                "name": "Vārda diena",
                "created_at": "2026-09-24T10:00:00+00:00",
                "updated_at": "2026-09-24T10:00:00+00:00",
                "track_ids": [f"existing-name-{i}" for i in range(7)],
            },
            {
                "id": "playlist-folk",
                "name": "Tautas dziesmas",
                "created_at": "2026-09-24T10:00:00+00:00",
                "updated_at": "2026-09-24T10:00:00+00:00",
                "track_ids": [f"existing-folk-{i}" for i in range(12)],
            },
            {
                "id": "playlist-elizabete",
                "name": "Elizabetei",
                "created_at": "2026-09-24T10:00:00+00:00",
                "updated_at": "2026-09-24T10:00:00+00:00",
                "track_ids": [f"existing-elizabete-{i}" for i in range(10)],
            },
        ],
    }
    PLAYLISTS_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
