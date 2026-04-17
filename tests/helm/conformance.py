from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


EXPECTED_NAMESPACES = {
    "estategap-system",
    "estategap-data",
    "estategap-scraping",
    "estategap-ml",
    "estategap-gateway",
    "estategap-pipeline",
    "estategap-intelligence",
    "estategap-notifications",
    "monitoring",
}
REQUIRED_LABELS = {
    "app.kubernetes.io/name",
    "app.kubernetes.io/instance",
    "app.kubernetes.io/component",
    "app.kubernetes.io/part-of",
}
WORKDIR = Path(__file__).resolve().parents[2]


def render_chart() -> str:
    command = [
        "helm",
        "template",
        "estategap",
        "helm/estategap",
        "-f",
        "helm/estategap/values.yaml",
        "-f",
        "helm/estategap/values-test.yaml",
    ]
    result = subprocess.run(
        command,
        cwd=WORKDIR,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode)
    return result.stdout


def iter_images(node: Any) -> list[str]:
    images: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "image" and isinstance(value, str):
                images.append(value)
            else:
                images.extend(iter_images(value))
    elif isinstance(node, list):
        for item in node:
            images.extend(iter_images(item))
    return images


def container_failures(kind: str, name: str, containers: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    for container in containers:
      container_name = container.get("name", "<unnamed>")
      prefix = f"{kind}/{name} container {container_name}"
      resources = container.get("resources") or {}
      requests = resources.get("requests") or {}
      limits = resources.get("limits") or {}
      security_context = container.get("securityContext") or {}
      if not requests:
          failures.append(f"{prefix}: missing resources.requests")
      if not limits:
          failures.append(f"{prefix}: missing resources.limits")
      if security_context.get("runAsNonRoot") is not True:
          failures.append(f"{prefix}: securityContext.runAsNonRoot must be true")
      if not container.get("livenessProbe"):
          failures.append(f"{prefix}: missing livenessProbe")
      if not container.get("readinessProbe"):
          failures.append(f"{prefix}: missing readinessProbe")
    return failures


def main() -> int:
    manifest_text = sys.stdin.read()
    if not manifest_text.strip():
        manifest_text = render_chart()

    failures: list[str] = []
    documents = [doc for doc in yaml.safe_load_all(manifest_text) if isinstance(doc, dict)]

    for document in documents:
        kind = document.get("kind", "<unknown>")
        metadata = document.get("metadata") or {}
        name = metadata.get("name", "<unnamed>")
        namespace = metadata.get("namespace")
        labels = metadata.get("labels") or {}

        if kind != "Namespace":
            if namespace not in EXPECTED_NAMESPACES:
                failures.append(f"{kind}/{name}: namespace {namespace!r} is not in the allowed set")
            missing_labels = sorted(label for label in REQUIRED_LABELS if label not in labels)
            if missing_labels:
                failures.append(f"{kind}/{name}: missing labels {', '.join(missing_labels)}")

        for image in iter_images(document):
            if image.endswith(":latest"):
                failures.append(f"{kind}/{name}: image {image!r} must not use the latest tag")

        if kind in {"Deployment", "StatefulSet"}:
            spec = document.get("spec") or {}
            template = spec.get("template") or {}
            pod_spec = template.get("spec") or {}
            containers = pod_spec.get("containers") or []
            failures.extend(container_failures(kind, name, containers))

    if failures:
        for failure in failures:
            print(failure)
    return len(failures)


if __name__ == "__main__":
    raise SystemExit(main())
