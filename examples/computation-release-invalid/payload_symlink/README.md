Invalid symlink escape fixture.

The declared payload path is outputs/metrics.json. Tests replace that path with a symlink (or reparse point) that points outside the release root; verify_result_artifact_payload must reject it with payload_path_unsafe.
