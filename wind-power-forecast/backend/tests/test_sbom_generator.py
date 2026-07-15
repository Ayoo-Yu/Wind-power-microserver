import json
import subprocess
import sys
from pathlib import Path


def test_sbom_generator_includes_image_python_and_frontend_components(tmp_path):
    project_dir = Path(__file__).resolve().parents[2]
    script = project_dir / "deploy" / "generate-sbom.py"
    python_packages = tmp_path / "python-packages.json"
    image_metadata = tmp_path / "images.json"
    frontend_lock = tmp_path / "package-lock.json"
    output = tmp_path / "sbom.json"

    python_packages.write_text(
        json.dumps([{"name": "Flask", "version": "2.3.2"}]),
        encoding="utf-8",
    )
    image_metadata.write_text(
        json.dumps([{
            "name": "prediction",
            "reference": "wind-power-celery-worker:2026.07.15",
            "id": f"sha256:{'a' * 64}",
            "created": "2026-07-15T00:00:00Z",
            "repo_digests": [],
        }]),
        encoding="utf-8",
    )
    frontend_lock.write_text(
        json.dumps({
            "packages": {
                "": {"name": "wind-power-frontend", "version": "1.0.0"},
                "node_modules/vue": {"name": "vue", "version": "3.5.13"},
            }
        }),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            str(script),
            "--release-version", "2026.07.15-rc1",
            "--git-commit", "b" * 40,
            "--python-packages", str(python_packages),
            "--frontend-lock", str(frontend_lock),
            "--image-metadata", str(image_metadata),
            "--output", str(output),
        ],
        check=True,
    )

    document = json.loads(output.read_text(encoding="utf-8"))
    assert document["bomFormat"] == "CycloneDX"
    assert document["specVersion"] == "1.5"
    components = {(item["type"], item["name"], item["version"]) for item in document["components"]}
    assert ("container", "prediction", "wind-power-celery-worker:2026.07.15") in components
    assert ("library", "Flask", "2.3.2") in components
    assert ("library", "vue", "3.5.13") in components
