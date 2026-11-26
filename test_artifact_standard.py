import json
import pathlib
import tempfile
import unittest
import zipfile

from artifact_standard import build_manifest, package_zip, write_manifest


class ArtifactStandardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gdi04-artifact-")
        self.root = pathlib.Path(self.tmp.name)
        (self.root / "app").mkdir()
        (self.root / "app" / "index.html").write_text("synthetic artifact", encoding="utf-8")
        self.source_sha = "a" * 40

    def tearDown(self):
        self.tmp.cleanup()

    def test_builds_zip_and_manifest_with_complete_provenance(self):
        output = pathlib.Path(package_zip(self.root, ["app/index.html"], self.root / "dist" / "demo.zip"))
        manifest = build_manifest("demo", output, version="1.2.3", release_status="RELEASE_CANDIDATE",
                                  source_sha=self.source_sha, release_notes="Synthetic acceptance", qa_status="PASS",
                                  build_timestamp="2026-11-26T10:00:00Z")
        with zipfile.ZipFile(output) as archive:
            self.assertEqual(archive.read("app/index.html"), b"synthetic artifact")
        self.assertEqual(manifest["file_size"], output.stat().st_size)
        self.assertEqual(len(manifest["sha256"]), 64)
        manifest_path = self.root / "dist" / "manifest.json"
        write_manifest(manifest, manifest_path)
        self.assertEqual(json.loads(manifest_path.read_text()), manifest)
        self.assertEqual(manifest_path.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            write_manifest(manifest, manifest_path)

    def test_release_states_require_qa_and_specific_owner_approval(self):
        output = pathlib.Path(package_zip(self.root, ["app/index.html"], self.root / "demo.zip"))
        values = dict(version="1.0", source_sha=self.source_sha, release_notes="Release", build_timestamp="2026-11-26T10:00:00Z")
        with self.assertRaisesRegex(ValueError, "passing QA"):
            build_manifest("demo", output, release_status="RELEASE_CANDIDATE", qa_status="NOT_TESTED", **values)
        with self.assertRaisesRegex(ValueError, "Owner approval"):
            build_manifest("demo", output, release_status="APPROVED_RELEASE", qa_status="PASS", **values)
        manifest = build_manifest("demo", output, release_status="APPROVED_RELEASE", qa_status="PASS", owner_release_approval="owner-release-1", **values)
        self.assertEqual(manifest["owner_release_approval"], "owner-release-1")

    def test_accepts_a_valid_prebuilt_apk_for_manifesting(self):
        apk = pathlib.Path(package_zip(self.root, ["app/index.html"], self.root / "demo.apk"))
        manifest = build_manifest("demo", apk, version="2.0", release_status="TESTING",
                                  source_sha=self.source_sha, release_notes="Synthetic APK", qa_status="NOT_TESTED")
        self.assertEqual(manifest["artifact_filename"], "demo.apk")

    def test_rejects_traversal_symlink_missing_metadata_and_invalid_apk(self):
        with self.assertRaisesRegex(ValueError, "traverse"):
            package_zip(self.root, ["../outside"], self.root / "bad.zip")
        (self.root / "link").symlink_to(self.root / "app" / "index.html")
        with self.assertRaisesRegex(ValueError, "symlinks"):
            package_zip(self.root, ["link"], self.root / "link.zip")
        bad = self.root / "bad.apk"
        bad.write_bytes(b"PK\x03\x04not a zip")
        with self.assertRaisesRegex(ValueError, "archive is invalid"):
            build_manifest("demo", bad, version="1", release_status="TESTING", source_sha=self.source_sha,
                           release_notes="Synthetic", qa_status="NOT_TESTED")


if __name__ == "__main__":
    unittest.main()
