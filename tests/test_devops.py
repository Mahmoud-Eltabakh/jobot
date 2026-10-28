import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def test_dockerfile_syntax() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM python:3.11-slim" in dockerfile
    assert "USER appuser" in dockerfile
    assert "playwright install" in dockerfile.lower()
    assert "HEALTHCHECK" in dockerfile
    assert "uvicorn" in dockerfile
    assert (ROOT / "Dockerfile.dev").exists()


def test_dockerignore_rules() -> None:
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    for pattern in [".venv", "data/", "__pycache__", ".git", ".pytest_cache"]:
        assert pattern in dockerignore


def test_docker_compose_config() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    assert {"jobot", "ollama"}.issubset(set(compose["services"]))
    assert "jobot_data" in compose["volumes"]
    assert "ollama_storage" in compose["volumes"]
    jobot = compose["services"]["jobot"]
    assert "8000:8000" in jobot["ports"]
    assert any("JOBOT_OLLAMA_BASE_URL" in item for item in jobot["environment"])
    assert jobot.get("pull_policy") == "build"

    # Host Ollama compose
    host_compose = yaml.safe_load((ROOT / "docker-compose.host-ollama.yml").read_text(encoding="utf-8"))
    assert "jobot" in host_compose["services"]
    assert "ollama" not in host_compose.get("services", {})
    assert any("host.docker.internal" in item for item in host_compose["services"]["jobot"]["environment"])


def test_k8s_manifests() -> None:
    k8s_dir = ROOT / "k8s"
    files = sorted(k8s_dir.glob("*.yaml"))
    assert len(files) >= 8
    merged = "\n---\n".join(path.read_text(encoding="utf-8") for path in files)
    assert "kind: Namespace" in merged
    assert "name: jobot" in merged
    assert "jobot-data-pvc" in merged
    assert "ollama-models-pvc" in merged
    assert "livenessProbe" in merged
    assert "readinessProbe" in merged


def test_scripts_exist_and_executable() -> None:
    expected = [
        "build.sh",
        "build.ps1",
        "run-docker.sh",
        "run-docker.ps1",
        "deploy-k8s.sh",
        "deploy-k8s.ps1",
    ]
    scripts_dir = ROOT / "scripts"
    for name in expected:
        path = scripts_dir / name
        assert path.exists(), f"Missing script: {name}"

    bash_paths = [scripts_dir / "build.sh", scripts_dir / "run-docker.sh", scripts_dir / "deploy-k8s.sh"]
    for path in bash_paths:
        text = path.read_text(encoding="utf-8")
        assert text.startswith("#!/usr/bin/env bash")
        assert "set -e" in text

    powershell_paths = [scripts_dir / "build.ps1", scripts_dir / "run-docker.ps1", scripts_dir / "deploy-k8s.ps1"]
    for path in powershell_paths:
        text = path.read_text(encoding="utf-8")
        assert text.lstrip().startswith("<#")
        assert "$ErrorActionPreference = \"Stop\"" in text


def _env_pairs(items) -> dict[str, str]:
    return dict(item.split("=", 1) for item in items)


def test_declared_jobot_env_reaches_settings(monkeypatch) -> None:
    from app.core.config import Settings

    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    declared = _env_pairs(compose["services"]["jobot"]["environment"])
    for key in [k for k in os.environ if k.startswith("JOBOT_") or k in {"OLLAMA_BASE_URL", "OLLAMA_MODEL", "ENV"}]:
        monkeypatch.delenv(key, raising=False)
    for key, value in declared.items():
        monkeypatch.setenv(key, value)
    settings = Settings(_env_file=None)
    assert settings.ollama_base_url == "http://ollama:11434"
    assert settings.ollama_model == declared["JOBOT_OLLAMA_MODEL"]
    assert settings.env == "production"


def test_unprefixed_env_overrides_prefixed(monkeypatch) -> None:
    from app.core.config import Settings

    monkeypatch.setenv("JOBOT_OLLAMA_MODEL", "prefixed")
    monkeypatch.setenv("OLLAMA_MODEL", "plain")
    assert Settings(_env_file=None).ollama_model == "plain"


def test_k8s_configmap_keys_map_to_settings(monkeypatch) -> None:
    from app.core.config import Settings

    for path in (ROOT / "k8s" / "configmap.yaml", ROOT / "k8s" / "jobot-all.yaml"):
        docs = [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d and d.get("kind") == "ConfigMap"]
        data = docs[0]["data"]
        for key, value in data.items():
            monkeypatch.setenv(key, value)
        settings = Settings(_env_file=None)
        assert settings.ollama_base_url == data["JOBOT_OLLAMA_BASE_URL"]
        assert settings.scraper_default_interval_hours == int(data["JOBOT_SCRAPER_DEFAULT_INTERVAL_HOURS"])


def _health_paths() -> set[str]:
    from app.main import app

    return {getattr(route, "path", "") for route in app.routes}


def test_health_probes_target_existing_route() -> None:
    import re

    assert "/health" in _health_paths()
    assert "/api/health" not in _health_paths()
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    healthcheck = re.search(r"HEALTHCHECK.*?localhost:8000(\S+)", dockerfile, re.S)
    assert healthcheck and healthcheck.group(1) in _health_paths()
    for name in ("deployment-jobot.yaml", "jobot-all.yaml"):
        text = (ROOT / "k8s" / name).read_text(encoding="utf-8")
        paths = set(re.findall(r"path: (/\S+)\n\s+port: 8000", text))
        assert paths and paths <= _health_paths(), (name, paths)


def test_ollama_model_prepull_declared() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    pull = compose["services"]["ollama-pull"]
    command = " ".join(pull["entrypoint"])
    model = _env_pairs(compose["services"]["jobot"]["environment"])["JOBOT_OLLAMA_MODEL"]
    assert f"ollama pull {model}" in command and "ollama pull nomic-embed-text" in command
    assert compose["services"]["jobot"]["depends_on"]["ollama-pull"]["condition"] == "service_completed_successfully"
    for name in ("deployment-ollama.yaml", "jobot-all.yaml"):
        text = (ROOT / "k8s" / name).read_text(encoding="utf-8")
        assert "postStart" in text and "ollama pull nomic-embed-text" in text and "ollama pull qwen2.5:7b" in text
