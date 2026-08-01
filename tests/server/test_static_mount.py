"""Static frontend mount tests that do not depend on a developer build."""

from pathlib import Path

from fastapi.testclient import TestClient

import main
import server.app as app_module


def _patch_successful_preflight(monkeypatch) -> None:
    monkeypatch.setattr(main, "run_startup_preflight", lambda: None)


def test_frontend_dist_is_repository_relative_and_cwd_independent(monkeypatch, tmp_path):
    expected_root = Path(app_module.__file__).resolve().parents[1]
    original_dist = app_module.FRONTEND_DIST

    monkeypatch.chdir(tmp_path)

    assert app_module.PROJECT_ROOT == expected_root
    assert original_dist == expected_root / "frontend" / "dist"
    assert original_dist.is_absolute()
    assert app_module.FRONTEND_DIST == original_dist


def test_existing_frontend_build_is_mounted_and_served(monkeypatch, tmp_path):
    _patch_successful_preflight(monkeypatch)
    frontend_dist = tmp_path / "frontend" / "dist"
    frontend_dist.mkdir(parents=True)
    frontend_dist.joinpath("index.html").write_text(
        "<html><body>STATIC-FRONTEND-MARKER</body></html>",
        encoding="utf-8",
    )
    monkeypatch.setattr(app_module, "FRONTEND_DIST", frontend_dist)

    with TestClient(app_module.create_app()) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "STATIC-FRONTEND-MARKER" in response.text


def test_missing_frontend_build_starts_api_only_without_exposing_path(
    monkeypatch, tmp_path, capsys
):
    _patch_successful_preflight(monkeypatch)
    missing_dist = tmp_path / "private-location" / "frontend" / "dist"
    monkeypatch.setattr(app_module, "FRONTEND_DIST", missing_dist)

    application = app_module.create_app()
    output = capsys.readouterr().out

    assert output.strip() == app_module.FRONTEND_BUILD_MISSING_MESSAGE
    assert str(tmp_path) not in output

    with TestClient(application) as client:
        api_response = client.get("/api/runs")
        root_response = client.get("/")

    assert api_response.status_code == 200
    assert api_response.json()["runs"] == []
    assert root_response.status_code == 404
