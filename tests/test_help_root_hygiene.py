from pathlib import Path

from ls_core.root_hygiene import organize_ls_root


def test_generated_patch_notes_are_archived_without_touching_user_files(tmp_path):
    root = tmp_path / "LS"
    root.mkdir()
    data = root / "Data"
    logs = root / "Logs"
    reports = root / "Reports"
    backup = root / "Backup"
    temp = root / "Temp"
    tools = root / "Tools"

    (root / "README_v2.10.txt").write_text("patch note", encoding="utf-8")
    (root / "README_PATCH.txt").write_text("older patch note", encoding="utf-8")
    (root / "SHA256SUMS.txt").write_text("hashes", encoding="utf-8")
    (root / "README.md").write_text("source readme", encoding="utf-8")
    (root / "LocalDB.txt").write_text("user note", encoding="utf-8")
    (root / "PowerShell.txt").write_text("user note", encoding="utf-8")

    result = organize_ls_root(
        host_root=root,
        app_dir=root,
        data_dir=data,
        logs_dir=logs,
        reports_dir=reports,
        backup_dir=backup,
        temp_dir=temp,
        tools_dir=tools,
    )

    package_notes = reports / "PackageNotes"
    assert (package_notes / "README_v2.10.txt").read_text(encoding="utf-8") == "patch note"
    assert (package_notes / "README_PATCH.txt").read_text(encoding="utf-8") == "older patch note"
    assert (package_notes / "SHA256SUMS.txt").read_text(encoding="utf-8") == "hashes"
    assert not (root / "README_v2.10.txt").exists()
    assert not (root / "README_PATCH.txt").exists()
    assert not (root / "SHA256SUMS.txt").exists()

    assert (root / "README.md").read_text(encoding="utf-8") == "source readme"
    assert (root / "LocalDB.txt").read_text(encoding="utf-8") == "user note"
    assert (root / "PowerShell.txt").read_text(encoding="utf-8") == "user note"
    assert len(result["moved"]) == 3


def test_help_sidebar_opens_styled_help_page():
    template = Path("ls_library/templates/library.html").read_text(encoding="utf-8")

    assert 'class="ls-sidebar-bottom-item" href="/help" title="Help"' in template
    assert 'id="open-help-modal"' not in template
