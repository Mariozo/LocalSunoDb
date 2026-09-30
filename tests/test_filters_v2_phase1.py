from pathlib import Path


def test_filters_v2_phase1_layout_and_routing_contract():
    template = Path("ls_library/templates/library.html").read_text(encoding="utf-8")
    handler = Path("ls_web/handler.py").read_text(encoding="utf-8")
    pages = Path("ls_web/pages.py").read_text(encoding="utf-8")
    repository = Path("ls_data/repository.py").read_text(encoding="utf-8")
    saved_views = Path(
        "ls_library/static/suno_saved_views_script_assets.js"
    ).read_text(encoding="utf-8")
    layout_css = Path(
        "ls_library/static/suno_filter_layout_dock_style_assets.css"
    ).read_text(encoding="utf-8")

    # Search, Filters, Active and Sort are separate visible zones.
    assert 'class="library-search-zone"' in template
    assert 'class="library-filter-zone-head"' in template
    assert 'class="library-control-row library-filters-v2-row"' in template
    assert 'class="library-control-row library-filters-v2-tools-row"' in template
    assert 'class="library-sort-group"' in template
    assert "library-zone-label" in layout_css
    assert "library-filters-v2-row" in layout_css
    assert "library-filters-v2-tools-row" in layout_css
    assert "left: 0;" in layout_css

    # Phase 1 quick dimensions are separate from Type / Operation.
    assert 'name="local_wav_filter"' in template
    assert 'name="upload_filter"' in template
    assert 'name="like_filter"' in template
    assert 'name="kind_filter"' in template
    assert "Type / Operation" in template

    # Upload must remain a broad canonical source identity, not an operation alias.
    assert "def _canonical_is_upload_sql" in repository
    assert 'lower(TRIM(COALESCE({track_alias}.source_type, \'\'))) = \'upload\'' in repository
    assert 'upload_filter in {"with", "without"}' in repository
    assert 'ui_type in ("Song", "Instrumental", "Upload")' in pages or (
        'ui_type in ("Song", "Instrumental", "Upload")' in Path(
            "ls_library/render.py"
        ).read_text(encoding="utf-8")
    )

    # Every quick dimension is threaded through main, lazy rows and exact count routes.
    for source in (handler, pages):
        assert "like_filter" in source
        assert "upload_filter" in source
        assert "local_wav_filter" in source

    # Saved Views preserve the three new quick filters.
    assert '"upload_filter"' in saved_views
    assert '"like_filter"' in saved_views
    assert '"local_wav_filter"' in saved_views
    for key in ("upload_filter", "like_filter", "local_wav_filter"):
        assert f'"{key}"' in repository
