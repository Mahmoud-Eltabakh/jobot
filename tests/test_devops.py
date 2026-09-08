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
