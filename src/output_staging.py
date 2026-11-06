from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path, PureWindowsPath


class OutputStager:
    """Stage a run's outputs and publish them as one directory replacement."""

    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir).resolve()
        self.staging_root = self.output_dir.parent / (
            f".{self.output_dir.name}.staging"
        )
        self.staging_root.mkdir(parents=True, exist_ok=True)
        self.staging_dir = Path(
            tempfile.mkdtemp(prefix="run-", dir=self.staging_root)
        )
        self._published = False

    def path_for(self, relative_path: str | Path) -> Path:
        """Return a safe path inside this run's staging directory."""
        raw_path = str(relative_path)
        candidate_path = Path(relative_path)
        windows_path = PureWindowsPath(raw_path)
        if (
            raw_path in ("", ".")
            or candidate_path.is_absolute()
            or windows_path.is_absolute()
            or windows_path.drive
            or ".." in candidate_path.parts
            or ".." in windows_path.parts
        ):
            raise ValueError("Staged output path must be relative to the staging directory.")

        destination = (self.staging_dir / candidate_path).resolve()
        try:
            destination.relative_to(self.staging_dir.resolve())
        except ValueError as exc:
            raise ValueError(
                "Staged output path must remain inside the staging directory."
            ) from exc
        destination.parent.mkdir(parents=True, exist_ok=True)
        return destination

    def preserve_failed_report(
        self, contents: str | bytes, filename: str = "validation_failed.csv"
    ) -> Path:
        """Persist a failure report in the retained staging run directory."""
        report_path = self.path_for(filename)
        if isinstance(contents, bytes):
            report_path.write_bytes(contents)
        else:
            report_path.write_text(contents, encoding="utf-8", newline="")
        return report_path

    def publish(self) -> None:
        """Replace final outputs with staged outputs, restoring old outputs on error."""
        if self._published:
            raise RuntimeError("This staging run has already been published.")
        if not any(self.staging_dir.iterdir()):
            raise RuntimeError("Cannot publish an empty staging directory.")

        backup_dir = self.output_dir.parent / (
            f".{self.output_dir.name}.backup-{uuid.uuid4().hex}"
        )
        had_previous_output = self.output_dir.exists() or self.output_dir.is_symlink()
        if had_previous_output:
            os.replace(self.output_dir, backup_dir)

        try:
            os.replace(self.staging_dir, self.output_dir)
        except OSError:
            if had_previous_output:
                os.replace(backup_dir, self.output_dir)
            raise

        self._published = True
        if backup_dir.is_dir() and not backup_dir.is_symlink():
            shutil.rmtree(backup_dir)
        elif backup_dir.exists() or backup_dir.is_symlink():
            backup_dir.unlink()

    def discard(self) -> None:
        """Remove this run's staged files when they are no longer needed."""
        if self._published:
            raise RuntimeError("Published outputs cannot be discarded as a staging run.")
        shutil.rmtree(self.staging_dir)
