import sqlite3
import sys
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ls_data.local_suno_migration import create_schema


DATA_DIR = ROOT / "Data"
DB_PATH = DATA_DIR / "local_suno.db"
TEMP_DIR = ROOT / "Temp" / "direct-library-fixture"


def write_wav(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(8000)
        wav_file.writeframes(b"\x00\x00" * 8000)


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    create_schema(conn)

    tasks = ("Cover", "Generate", "Extend")
    workspaces = ("Studio A", "Studio B", "Studio C")

    for index in range(1, 76):
        track_id = f"canon-{index:03d}"
        title = f"Canonical Track {index:03d}"
        if index == 1:
            title = "Alpha Search Song"
        elif index == 2:
            title = "Manual Category Override"
        elif index == 3:
            title = "Local Playback Track"

        workspace = workspaces[(index - 1) % len(workspaces)]
        source_task = tasks[(index - 1) % len(tasks)]
        kind = "Song" if index % 2 else "Instrumental"
        manual_category = ""
        if index == 2:
            kind = "Song"
            manual_category = "Instrumental"

        liked = 1 if index in (1, 2, 3) or index % 5 == 0 else 0
        if index == 1:
            marks = 5
            tags = "#rock, #live"
            rating = 5
        elif index == 2:
            marks = 1
            tags = "#rock"
            rating = 4
        elif index % 7 == 0:
            marks = 2
            tags = "#ambient"
            rating = 2
        else:
            marks = 0
            tags = ""
            rating = 0

        duration = 60.0 + index * 3.0
        created_at = f"2026-09-{1 + ((index - 1) % 24):02d}T{index % 24:02d}:00:00Z"
        style = "rock live" if index in (1, 2) else ("ambient" if index % 7 == 0 else "fixture")

        conn.execute(
            """
            INSERT INTO tracks(
                id,title,created_at,workspace_id,workspace_name,audio_url,
                image_url,image_large_url,model_name,major_model_version,
                source_type,source_task,style_tags,prompt,duration_seconds,
                avg_bpm,is_liked,display_tags,kind,lyrics,library_status,finder_hidden
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)
            """,
            (
                track_id,
                title,
                created_at,
                "ws-" + workspace[-1].lower(),
                workspace,
                f"https://example.invalid/{track_id}.mp3",
                "",
                "",
                "chirp-crow",
                "v5.5",
                "gen",
                source_task,
                style,
                "fixture prompt " + title,
                duration,
                90.0 + (index % 40),
                liked,
                style,
                kind,
                "fixture lyrics " + title,
                "active",
            ),
        )
        conn.execute(
            """
            INSERT INTO track_user(
                track_id,rating,tags,marks,manual_category,updated_at
            ) VALUES (?,?,?,?,?,'2026-09-25T09:00:00Z')
            """,
            (track_id, rating, tags, marks, manual_category),
        )

        has_local = index == 1 or index % 3 == 0
        if has_local:
            audio_path = TEMP_DIR / f"{track_id}.wav"
            write_wav(audio_path)
            variant = conn.execute(
                """
                INSERT INTO track_variants(
                    track_id,variant_no,label,folder_path,variant_kind
                ) VALUES (?,1,'1',?,'main')
                """,
                (track_id, str(TEMP_DIR)),
            )
            conn.execute(
                """
                INSERT INTO media_files(
                    variant_id,path,role,format,stem_label,size_bytes,modified_at,
                    file_created_at,file_created_at_source,chronology_at
                ) VALUES (?,?,'main','wav','',16000,'2026-09-25T09:00:00Z',
                          '2026-09-25T09:00:00Z','modified_time','2026-09-25T09:00:00Z')
                """,
                (variant.lastrowid, str(audio_path)),
            )
            if index == 1:
                stem_path = TEMP_DIR / f"{track_id} (Vocals).wav"
                write_wav(stem_path)
                conn.execute(
                    """
                    INSERT INTO media_files(
                        variant_id,path,role,format,stem_label,size_bytes,modified_at,
                        file_created_at,file_created_at_source,chronology_at
                    ) VALUES (?,?,'stem','wav','Vocals',16000,'2026-09-25T09:00:00Z',
                              '2026-09-25T09:00:00Z','modified_time','2026-09-25T09:00:00Z')
                    """,
                    (variant.lastrowid, str(stem_path)),
                )

    conn.execute(
        """
        INSERT INTO tracks(
            id,title,workspace_name,source_task,kind,library_status,finder_hidden
        ) VALUES ('canon-hidden','Hidden Canonical Track','Studio A','Cover','Song','active',1)
        """
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
