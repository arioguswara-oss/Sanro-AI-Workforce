"""Project-scoped ZIP/APK packaging and release-manifest validation."""
import hashlib
import json
import os
import pathlib
import re
import stat
import zipfile
from datetime import datetime, timezone

SHA_RE = re.compile(r"^(?:[a-f0-9]{40}|[a-f0-9]{64})$")
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+_-]{0,63}$")
RELEASE_STATES = {"DEVELOPMENT", "TESTING", "RELEASE_CANDIDATE", "APPROVED_RELEASE"}
QA_STATES = {"PASS", "FAIL", "NOT_TESTED"}


def _inside(root, path):
    root = pathlib.Path(root).resolve(strict=True)
    candidate = pathlib.Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    if ".." in candidate.parts:
        raise ValueError("artifact path traversal is not allowed")
    cursor = pathlib.Path(candidate.anchor)
    for part in candidate.parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("artifact paths cannot contain symlinks")
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise ValueError("artifact path must stay inside the authorized project")
    return resolved


def package_zip(project_root, files, output_path):
    """Create a ZIP from explicitly enumerated project-relative regular files."""
    root = pathlib.Path(project_root).resolve(strict=True)
    output = _inside(root, output_path)
    if output.exists() or not isinstance(files, list) or not files:
        raise ValueError("ZIP output must be new and the explicit file list non-empty")
    entries = []
    for item in files:
        if not isinstance(item, str) or not item or "\\" in item:
            raise ValueError("ZIP entries must be project-relative paths")
        rel = pathlib.PurePosixPath(item)
        if rel.is_absolute() or ".." in rel.parts or "." in rel.parts:
            raise ValueError("ZIP entries must not traverse project paths")
        source = _inside(root, root / pathlib.Path(*rel.parts))
        info = source.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("ZIP entries must be regular files")
        entries.append((rel.as_posix(), source))
    if len({name for name, _ in entries}) != len(entries):
        raise ValueError("duplicate ZIP entry")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, source in sorted(entries):
            archive.write(source, name)
    return str(output)


def build_manifest(project_id, artifact_path, *, version, release_status, source_sha,
                   release_notes, qa_status, build_timestamp=None, owner_release_approval=None):
    path = pathlib.Path(artifact_path)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", str(project_id)):
        raise ValueError("invalid project ID")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.(?:zip|apk)", path.name, re.IGNORECASE):
        raise ValueError("artifact filename must be a ZIP or APK basename")
    if not path.is_file() or path.is_symlink():
        raise ValueError("artifact must be an existing regular file")
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
        raise ValueError("invalid artifact version")
    if release_status not in RELEASE_STATES or qa_status not in QA_STATES:
        raise ValueError("invalid release or QA status")
    if not isinstance(source_sha, str) or not SHA_RE.fullmatch(source_sha):
        raise ValueError("source commit SHA is required")
    if not isinstance(release_notes, str) or not release_notes.strip() or len(release_notes) > 4000:
        raise ValueError("bounded release notes are required")
    if release_status in {"RELEASE_CANDIDATE", "APPROVED_RELEASE"} and qa_status != "PASS":
        raise ValueError("release candidate requires passing QA")
    if release_status == "APPROVED_RELEASE" and (not isinstance(owner_release_approval, str) or len(owner_release_approval) < 8):
        raise ValueError("approved release requires a separate Owner approval reference")
    if build_timestamp is None:
        build_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    try:
        stamp = datetime.fromisoformat(build_timestamp.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError
    except (ValueError, AttributeError):
        raise ValueError("build timestamp must be an ISO-8601 timestamp with timezone") from None
    if not zipfile.is_zipfile(path):
        raise ValueError("ZIP/APK artifact archive is invalid")
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP/APK artifact contains a corrupt entry")
    size = path.stat().st_size
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return {
        "schema_version": 1, "project_id": project_id, "artifact_filename": path.name,
        "version": version, "release_status": release_status, "source_commit_sha": source_sha,
        "build_timestamp": stamp.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "file_size": size, "sha256": h.hexdigest(),
        "release_notes": release_notes.strip(), "qa_status": qa_status,
        "owner_release_approval": owner_release_approval if release_status == "APPROVED_RELEASE" else None,
    }


def write_manifest(manifest, output_path):
    required = {"schema_version", "project_id", "artifact_filename", "version", "release_status", "source_commit_sha", "build_timestamp", "file_size", "sha256", "release_notes", "qa_status", "owner_release_approval"}
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise ValueError("artifact manifest fields are missing or unexpected")
    if (manifest.get("schema_version") != 1 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", str(manifest.get("project_id", "")))
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.(?:zip|apk)", str(manifest.get("artifact_filename", "")), re.IGNORECASE)
            or not isinstance(manifest.get("version"), str) or not VERSION_RE.fullmatch(manifest["version"])
            or manifest.get("release_status") not in RELEASE_STATES or manifest.get("qa_status") not in QA_STATES
            or not isinstance(manifest.get("source_commit_sha"), str) or not SHA_RE.fullmatch(manifest["source_commit_sha"])
            or not isinstance(manifest.get("sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", manifest["sha256"])
            or not isinstance(manifest.get("file_size"), int) or isinstance(manifest.get("file_size"), bool) or manifest["file_size"] <= 0
            or not isinstance(manifest.get("release_notes"), str) or not manifest["release_notes"].strip() or len(manifest["release_notes"]) > 4000):
        raise ValueError("artifact manifest metadata is invalid")
    try:
        stamp = datetime.fromisoformat(manifest["build_timestamp"].replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError
    except (ValueError, AttributeError, KeyError):
        raise ValueError("artifact build timestamp is invalid") from None
    if manifest["release_status"] in {"RELEASE_CANDIDATE", "APPROVED_RELEASE"} and manifest["qa_status"] != "PASS":
        raise ValueError("release candidate requires passing QA")
    if manifest["release_status"] == "APPROVED_RELEASE" and (not isinstance(manifest.get("owner_release_approval"), str) or len(manifest["owner_release_approval"]) < 8):
        raise ValueError("approved release requires an Owner approval reference")
    if manifest["release_status"] != "APPROVED_RELEASE" and manifest.get("owner_release_approval") is not None:
        raise ValueError("Owner release approval is only valid for an approved release")
    path = pathlib.Path(output_path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    return str(path)
