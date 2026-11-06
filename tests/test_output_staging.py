import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.output_staging import OutputStager


class TestOutputStager(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.output_dir = self.root / "output"
        self.output_dir.mkdir()
        (self.output_dir / "previous.csv").write_text(
            "previous successful output\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_publish_replaces_outputs_only_after_requested(self) -> None:
        stager = OutputStager(self.output_dir)
        new_output = stager.path_for("canonical.csv")
        new_output.write_text("new canonical output\n", encoding="utf-8")

        self.assertTrue((self.output_dir / "previous.csv").exists())
        self.assertFalse((self.output_dir / "canonical.csv").exists())

        stager.publish()

        self.assertFalse((self.output_dir / "previous.csv").exists())
        self.assertEqual(
            (self.output_dir / "canonical.csv").read_text(encoding="utf-8"),
            "new canonical output\n",
        )
        self.assertFalse(stager.staging_dir.exists())
        with self.assertRaises(RuntimeError):
            stager.publish()

    def test_failed_run_keeps_old_outputs_and_failure_report(self) -> None:
        stager = OutputStager(self.output_dir)
        stager.path_for("partial.csv").write_text(
            "partial output\n", encoding="utf-8"
        )
        report_path = stager.preserve_failed_report(
            "check,pass\ninput_rows,false\n"
        )

        self.assertTrue(report_path.is_file())
        self.assertEqual(
            report_path.read_text(encoding="utf-8"),
            "check,pass\ninput_rows,false\n",
        )
        self.assertTrue((self.output_dir / "previous.csv").is_file())
        self.assertFalse((self.output_dir / "partial.csv").exists())
        self.assertTrue(stager.staging_dir.is_dir())

    def test_rejects_paths_outside_staging_directory(self) -> None:
        stager = OutputStager(self.output_dir)
        for unsafe_path in ("../escape.csv", r"..\escape.csv", r"C:\escape.csv"):
            with self.subTest(path=unsafe_path):
                with self.assertRaises(ValueError):
                    stager.path_for(unsafe_path)
        stager.discard()

    def test_publish_failure_restores_previous_outputs(self) -> None:
        stager = OutputStager(self.output_dir)
        stager.path_for("new.csv").write_text("new\n", encoding="utf-8")
        real_replace = __import__("os").replace
        replace_calls = 0

        def fail_stage_move_once(source: str | Path, destination: str | Path) -> None:
            nonlocal replace_calls
            replace_calls += 1
            if replace_calls == 2:
                raise OSError("simulated publication failure")
            real_replace(source, destination)

        with patch("src.output_staging.os.replace", side_effect=fail_stage_move_once):
            with self.assertRaisesRegex(OSError, "simulated publication failure"):
                stager.publish()

        self.assertEqual(replace_calls, 3)
        self.assertTrue((self.output_dir / "previous.csv").is_file())
        self.assertFalse((self.output_dir / "new.csv").exists())
        self.assertTrue(stager.staging_dir.is_dir())
        stager.discard()


if __name__ == "__main__":
    unittest.main()
