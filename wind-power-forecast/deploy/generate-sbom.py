"""根据实际业务镜像和前端锁文件生成 CycloneDX 应用 SBOM。"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _component_key(component: dict) -> tuple[str, str, str]:
    return (
        str(component.get("type") or "library"),
        str(component.get("name") or ""),
        str(component.get("version") or ""),
    )


def _python_components(package_path: Path) -> list[dict]:
    result = []
    for package in _load_json(package_path):
        name = str(package.get("name") or "").strip()
        version = str(package.get("version") or "").strip()
        if not name or not version:
            continue
        normalized = name.lower().replace("_", "-")
        result.append({
            "type": "library",
            "bom-ref": f"pkg:pypi/{quote(normalized)}@{quote(version)}",
            "name": name,
            "version": version,
            "purl": f"pkg:pypi/{quote(normalized)}@{quote(version)}",
            "properties": [{"name": "windpower:source", "value": "prediction-image"}],
        })
    return result


def _npm_components(lock_path: Path) -> list[dict]:
    lock = _load_json(lock_path)
    result = []
    for package_path, package in dict(lock.get("packages") or {}).items():
        if not package_path or "node_modules/" not in package_path:
            continue
        name = str(package.get("name") or package_path.rsplit("node_modules/", 1)[-1]).strip()
        version = str(package.get("version") or "").strip()
        if not name or not version:
            continue
        encoded_name = quote(name, safe="@/")
        purl = f"pkg:npm/{encoded_name}@{quote(version)}"
        result.append({
            "type": "library",
            "bom-ref": purl,
            "name": name,
            "version": version,
            "purl": purl,
            "scope": "required" if not package.get("dev") else "optional",
            "properties": [{"name": "windpower:source", "value": "frontend-package-lock"}],
        })
    return result


def _image_components(metadata_path: Path) -> list[dict]:
    result = []
    for image in _load_json(metadata_path):
        name = str(image.get("name") or "image")
        reference = str(image.get("reference") or "unknown")
        image_id = str(image.get("id") or "")
        component = {
            "type": "container",
            "bom-ref": f"urn:windpower:image:{quote(name)}:{quote(image_id or reference)}",
            "name": name,
            "version": reference,
            "properties": [
                {"name": "windpower:image-reference", "value": reference},
                {"name": "windpower:image-created", "value": str(image.get("created") or "")},
                {
                    "name": "windpower:repo-digests",
                    "value": ",".join(image.get("repo_digests") or []),
                },
            ],
        }
        if image_id.startswith("sha256:") and len(image_id) == 71:
            component["hashes"] = [{"alg": "SHA-256", "content": image_id.split(":", 1)[1]}]
        result.append(component)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-version", required=True)
    parser.add_argument("--git-commit", required=True)
    parser.add_argument("--python-packages", type=Path, required=True)
    parser.add_argument("--frontend-lock", type=Path, required=True)
    parser.add_argument("--image-metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    components = []
    components.extend(_image_components(args.image_metadata))
    components.extend(_python_components(args.python_packages))
    components.extend(_npm_components(args.frontend_lock))
    deduplicated = {}
    for component in components:
        deduplicated.setdefault(_component_key(component), component)
    components = sorted(deduplicated.values(), key=_component_key)

    serial_seed = f"{args.release_version}:{args.git_commit}"
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, serial_seed)}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tools": {
                "components": [{
                    "type": "application",
                    "name": "windpower-sbom-generator",
                    "version": "1.0",
                }],
            },
            "component": {
                "type": "application",
                "bom-ref": f"urn:windpower:release:{quote(args.release_version)}",
                "name": "wind-power-forecast",
                "version": args.release_version,
                "properties": [{"name": "windpower:git-commit", "value": args.git_commit}],
            },
        },
        "components": components,
    }
    args.output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
