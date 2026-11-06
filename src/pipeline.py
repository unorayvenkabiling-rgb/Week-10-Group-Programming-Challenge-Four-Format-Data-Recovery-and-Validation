from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.analysis import (
    compute_asia_selection,
    compute_independent_asian_total,
    compute_numpy_population_matrix,
    compute_philippines_summary,
)
from src.export_roundtrip import (
    compare_canonical_export,
    export_canonical_formats,
    verify_canonical_round_trips,
)
from src.json_parquet_loaders import load_json_records, load_parquet_records
from src.output_staging import OutputStager
from src.readers import load_csv_records, load_excel_records
from src.validation import validate_and_quarantine, validate_row


CANONICAL_COLUMNS = [
    "country",
    "continent",
    "year",
    "lifeExp",
    "pop",
    "gdpPercap",
]
REPORT_COLUMNS = ["check", "expected", "actual", "tolerance", "pass"]
AUDIT_COLUMNS = [
    "step",
    "source_file",
    "operation",
    "rule",
    "rows_before",
    "rows_after",
]
QUARANTINE_COLUMNS = [
    "source_file",
    "source_record",
    "reason",
    *CANONICAL_COLUMNS,
]
DUPLICATE_COLUMNS = [
    "source_file",
    "source_record",
    "duplicate_of_source_record",
    *CANONICAL_COLUMNS,
]

READERS = {
    "csv": load_csv_records,
    "xlsx": load_excel_records,
    "json": load_json_records,
    "parquet": load_parquet_records,
}


class PipelineCheckError(RuntimeError):
    """Raised when an integration validation check fails."""

    def __init__(self, report: pd.DataFrame) -> None:
        self.report = report
        failures = report.loc[
            ~report["pass"], ["check", "actual"]
        ]
        super().__init__(
            "Pipeline validation failed:\n" + failures.to_string(index=False)
        )


class ProcessingRun:
    """Manage configuration, validation checks, audit records, and one run."""

    def __init__(self, config: dict[str, Any], config_dir: Path) -> None:
        self.config = config
        self.config_dir = config_dir
        self.validation_rows: list[dict[str, object]] = []
        self.audit_rows: list[dict[str, object]] = []

    def add_check(
        self,
        source_file: str,
        check: str,
        expected: object,
        actual: object,
        passed: bool,
        tolerance: object = 0,
    ) -> None:
        """Record one validation check in the required report schema."""
        check_name = f"{source_file}:{check}" if source_file else check
        self.validation_rows.append(
            {
                "check": check_name,
                "expected": expected,
                "actual": actual,
                "tolerance": tolerance,
                "pass": bool(passed),
            }
        )

    def add_audit(
        self,
        step: str,
        source_file: str,
        operation: str,
        rule: str,
        rows_before: int,
        rows_after: int,
    ) -> None:
        """Record one workflow event in the audit log."""
        self.audit_rows.append(
            {
                "step": step,
                "source_file": source_file,
                "operation": operation,
                "rule": rule,
                "rows_before": rows_before,
                "rows_after": rows_after,
            }
        )

    def run(self) -> int:
        """Execute this configured recovery and reporting run."""
        return _execute_processing(self)


def _resolve_path(value: str, config_dir: Path) -> Path:
    """Resolve a configured path relative to the config file."""
    path = Path(value)
    if not path.is_absolute():
        path = config_dir / path
    return path.resolve()


def _load_configuration(config_path: str | Path) -> tuple[dict[str, Any], Path]:
    """Load JSON configuration and return it with its containing directory."""
    resolved_config = Path(config_path).resolve()
    with resolved_config.open("r", encoding="utf-8") as file:
        config = json.load(file)
    if not isinstance(config, dict):
        raise ValueError("Configuration file must contain a JSON object.")
    return config, resolved_config.parent


def _input_path(
    config: dict[str, Any], data_dir: Path, format_name: str
) -> Path:
    """Resolve an input file named by the project configuration."""
    config_key = "excel_file" if format_name == "xlsx" else f"{format_name}_file"
    filename = config.get(config_key)
    if not isinstance(filename, str) or not filename:
        raise ValueError(f"Configuration must define {config_key}.")
    configured_path = Path(filename)
    if configured_path.is_absolute():
        return configured_path
    return data_dir / configured_path


def _duplicate_log(
    raw_df: pd.DataFrame,
    manifest: dict[str, Any],
    source_file: str,
) -> pd.DataFrame:
    """Record each valid exact duplicate and the earlier source record."""
    canonical = manifest["canonical_order"]
    valid_rows: list[dict[str, object]] = []
    for position, (_, row) in enumerate(raw_df.iterrows(), start=1):
        if not validate_row(row, manifest):
            record = {column: row[column] for column in canonical}
            record["source_record"] = position
            valid_rows.append(record)

    if not valid_rows:
        return pd.DataFrame(columns=DUPLICATE_COLUMNS)

    valid_df = pd.DataFrame(valid_rows)
    duplicate_mask = valid_df.duplicated(subset=canonical, keep="first")
    seen: dict[tuple[object, ...], int] = {}
    duplicates = []
    for _, row in valid_df.iterrows():
        key = tuple(row[column] for column in canonical)
        source_record = int(row["source_record"])
        if key in seen:
            duplicates.append(
                {
                    "source_file": source_file,
                    "source_record": source_record,
                    "duplicate_of_source_record": seen[key],
                    **{column: row[column] for column in canonical},
                }
            )
        else:
            seen[key] = source_record

    duplicate_records = pd.DataFrame(duplicates, columns=DUPLICATE_COLUMNS)
    if len(duplicate_records) != int(duplicate_mask.sum()):
        raise RuntimeError("Duplicate audit count differs from exact deduplication.")
    return duplicate_records


def _quarantine_log(
    quarantine_df: pd.DataFrame, source_file: str
) -> pd.DataFrame:
    """Shape validator output to the required quarantine CSV schema."""
    if quarantine_df.empty:
        return pd.DataFrame(columns=QUARANTINE_COLUMNS)
    result = quarantine_df.copy()
    result["source_file"] = source_file
    if "source_record" not in result.columns:
        raise ValueError("Validator did not preserve source record positions.")
    result["reason"] = result["quarantine_reason"]
    return result[QUARANTINE_COLUMNS]


def _append_comparison_report(
    run: ProcessingRun, report: pd.DataFrame
) -> None:
    for item in report.to_dict(orient="records"):
        run.add_check(
            str(item.get("source_file", item.get("file", ""))),
            str(item["check"]),
            item.get("expected"),
            item.get("actual"),
            bool(item["pass"]),
            item.get("tolerance", 0),
        )


def _analysis_outputs(
    canonical_df: pd.DataFrame,
    reporting_year: int,
    staging_dir: Path,
    manifest: dict[str, Any],
    run: ProcessingRun,
) -> None:
    """Write analytical result files and add their validation/audit records."""
    asia_df = compute_asia_selection(canonical_df, reporting_year)
    asia_df.to_csv(staging_dir / "asia_selected_year.csv", index=False)
    run.add_audit(
        "analysis",
        "",
        "select and rank Asia; calculate population in millions",
        f"reporting year {reporting_year}; descending life expectancy, min rank",
        len(canonical_df),
        len(asia_df),
    )
    asia_expected = int(
        canonical_df.loc[
            (canonical_df["continent"] == "Asia")
            & (canonical_df["year"] == reporting_year)
        ].shape[0]
    )
    run.add_check(
        "",
        "asia_selected_row_count",
        asia_expected,
        len(asia_df),
        len(asia_df) == asia_expected,
    )

    philippine_df = compute_philippines_summary(canonical_df)
    philippine_df.to_csv(staging_dir / "country_history.csv", index=False)
    run.add_audit(
        "analysis",
        "",
        "select Philippines and calculate history changes",
        "all observations sorted by year; change from first observation",
        len(canonical_df),
        len(philippine_df),
    )
    expected_philippine_rows = int(
        manifest["controls"]["philippines_rows"]
    )
    run.add_check(
        "",
        "philippines_observation_count",
        expected_philippine_rows,
        len(philippine_df),
        len(philippine_df) == expected_philippine_rows,
    )

    matrix_result = compute_numpy_population_matrix(canonical_df)
    year_names = [str(year) for year in matrix_result["years"]]
    matrix_df = pd.DataFrame(
        matrix_result["broadcasted_matrix"],
        columns=year_names,
    )
    matrix_df.insert(0, "country", matrix_result["countries"])
    matrix_df.to_csv(staging_dir / "population_index.csv", index=False)
    run.add_audit(
        "analysis",
        "",
        "build and broadcast NumPy population index",
        "countries Philippines, Indonesia, Thailand; baseline 1982=100",
        matrix_result["shape_before"][0] * matrix_result["shape_before"][1],
        matrix_result["shape_after"][0] * matrix_result["shape_after"][1],
    )

    expected_raw_matrix = (
        canonical_df.loc[
            canonical_df["country"].isin(matrix_result["countries"])
            & canonical_df["year"].isin(matrix_result["years"])
        ]
        .pivot(index="country", columns="year", values="pop")
        .reindex(
            index=matrix_result["countries"],
            columns=matrix_result["years"],
        )
        .to_numpy(dtype=float)
    )
    loop_matrix = np.empty_like(expected_raw_matrix)
    for row_index in range(expected_raw_matrix.shape[0]):
        baseline = expected_raw_matrix[row_index, 0]
        for column_index in range(expected_raw_matrix.shape[1]):
            loop_matrix[row_index, column_index] = (
                expected_raw_matrix[row_index, column_index] / baseline * 100
            )
    broadcast_matches_loop = np.allclose(
        matrix_result["broadcasted_matrix"],
        loop_matrix,
        rtol=0,
        atol=1e-8,
    )
    run.add_check(
        "",
        "numpy_shape_before",
        (3, 6),
        matrix_result["shape_before"],
        matrix_result["shape_before"] == (3, 6),
    )
    run.add_check(
        "",
        "numpy_shape_after",
        (3, 6),
        matrix_result["shape_after"],
        matrix_result["shape_after"] == (3, 6),
    )
    run.add_check(
        "",
        "numpy_broadcast_loop_agreement",
        True,
        broadcast_matches_loop,
        broadcast_matches_loop,
        1e-8,
    )
    baseline_values = matrix_result["broadcasted_matrix"][:, 0]
    baseline_matches = bool(np.isclose(baseline_values, 100, rtol=0, atol=1e-8).all())
    run.add_check(
        "",
        "numpy_1982_baseline",
        "all rows equal 100",
        baseline_values.tolist(),
        baseline_matches,
        1e-8,
    )
    selection_mask = expected_raw_matrix[:, -1] > 70_000_000
    expected_selected = np.array(matrix_result["countries"])[selection_mask].tolist()
    expected_mean = float(np.mean(expected_raw_matrix[selection_mask, -1]))
    mean_matches = bool(
        np.isclose(
            expected_mean,
            matrix_result["mean_pop_large_countries_2007"],
            rtol=0,
            atol=1e-8,
        )
    )
    selection_matches = (
        expected_selected == matrix_result["filtered_countries_2007"]
        and mean_matches
    )
    run.add_check(
        "",
        "numpy_boolean_selection_and_mean",
        f"{expected_selected}; mean={expected_mean}",
        f"{matrix_result['filtered_countries_2007']}; "
        f"mean={matrix_result['mean_pop_large_countries_2007']}",
        selection_matches,
    )

    pandas_asia_total = int(
        canonical_df.loc[
            (canonical_df["continent"] == "Asia")
            & (canonical_df["year"] == reporting_year),
            "pop",
        ].sum()
    )
    numpy_asia_total = compute_independent_asian_total(
        canonical_df, reporting_year
    )
    run.add_check(
        "",
        "selected_year_asian_population_total",
        pandas_asia_total,
        numpy_asia_total,
        pandas_asia_total == numpy_asia_total,
    )
    if reporting_year == 2007:
        expected_total = int(manifest["controls"]["asia_2007_population"])
        run.add_check(
            "",
            "asia_2007_population_control",
            expected_total,
            numpy_asia_total,
            numpy_asia_total == expected_total,
        )

    expected_ph_population = int(
        manifest["controls"]["philippines_2007_population"]
    )
    actual_ph_population = int(
        philippine_df.loc[philippine_df["year"] == 2007, "pop"].iloc[0]
    )
    run.add_check(
        "",
        "philippines_2007_population_control",
        expected_ph_population,
        actual_ph_population,
        actual_ph_population == expected_ph_population,
    )
def _report_from_exception(
    error: Exception, run: ProcessingRun
) -> pd.DataFrame:
    """Build a failed validation report from accumulated checks and an error."""
    report_rows = list(run.validation_rows)
    exception_report = getattr(error, "report", None)
    if isinstance(error, PipelineCheckError):
        report_rows = exception_report.to_dict(orient="records")
    elif isinstance(exception_report, pd.DataFrame):
        temporary_run = ProcessingRun(run.config, run.config_dir)
        _append_comparison_report(temporary_run, exception_report)
        report_rows.extend(temporary_run.validation_rows)
    failure_run = ProcessingRun(run.config, run.config_dir)
    failure_run.validation_rows = report_rows
    failure_run.add_check(
        "",
        "processing",
        "complete without errors",
        f"{type(error).__name__}: {error}",
        False,
    )
    return pd.DataFrame(failure_run.validation_rows, columns=REPORT_COLUMNS)


def run_pipeline(config_path: str | Path) -> int:
    """Run recovery, agreement, analysis, export verification, and publishing."""
    try:
        config, config_dir = _load_configuration(config_path)
    except Exception as exc:
        print(f"Processing failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return ProcessingRun(config, config_dir).run()


def _execute_processing(run: ProcessingRun) -> int:
    """Execute processing and report/publish results for one run."""
    stager: OutputStager | None = None
    validation_rows = run.validation_rows
    audit_rows = run.audit_rows
    try:
        config = run.config
        config_dir = run.config_dir
        data_dir = _resolve_path(config.get("data_folder", "data"), config_dir)
        output_dir = _resolve_path(
            config.get("output_folder", "outputs"), config_dir
        )
        stager = OutputStager(output_dir)
        manifest_path = _resolve_path(
            str(config.get("manifest_file", "manifest.json")), data_dir
        )
        with manifest_path.open("r", encoding="utf-8") as file:
            manifest = json.load(file)

        reporting_year = config.get("reporting_year", config.get("default_year", 2007))
        if isinstance(reporting_year, bool) or not isinstance(reporting_year, int):
            raise ValueError("reporting_year must be an integer.")

        canonical_columns = manifest.get("canonical_order")
        if canonical_columns != CANONICAL_COLUMNS:
            raise ValueError(
                f"Manifest canonical_order must be {CANONICAL_COLUMNS}."
            )
        if not manifest.get("files"):
            raise ValueError("Manifest must list the four configured input files.")

        cleaned_by_source: dict[str, pd.DataFrame] = {}
        quarantine_logs = []
        duplicate_logs = []
        for file_config in manifest["files"]:
            format_name = file_config.get("format")
            manifest_filename = file_config.get("file")
            if format_name not in READERS or not isinstance(manifest_filename, str):
                raise ValueError(f"Unsupported or invalid manifest input: {file_config!r}")
            configured_path = _input_path(config, data_dir, format_name)
            raw_df = READERS[format_name](configured_path, manifest)
            source_file = configured_path.name
            raw_count = len(raw_df)
            if list(raw_df.columns) != canonical_columns:
                raise ValueError(
                    f"{source_file} did not return the canonical schema."
                )

            quarantine_source = raw_df.copy()
            quarantine_source["source_file"] = source_file
            quarantine_source["source_record"] = np.arange(
                1, raw_count + 1, dtype=np.int64
            )
            clean_df, quarantine_df = validate_and_quarantine(
                quarantine_source, manifest
            )
            clean_df = clean_df.sort_values(
                ["country", "year"], kind="stable"
            ).reset_index(drop=True)
            quarantine_log = _quarantine_log(quarantine_df, source_file)
            duplicate_log = _duplicate_log(raw_df, manifest, source_file)
            quarantine_logs.append(quarantine_log)
            duplicate_logs.append(duplicate_log)
            cleaned_by_source[source_file] = clean_df

            expected_counts = manifest["expected_per_file"]
            rejected_count = len(quarantine_log)
            duplicate_count = len(duplicate_log)
            reconciliation_passes = (
                raw_count
                == rejected_count + duplicate_count + len(clean_df)
                and raw_count == expected_counts["raw_rows"]
                and rejected_count == expected_counts["rejected_rows"]
                and duplicate_count == expected_counts["exact_duplicates_removed"]
                and len(clean_df) == expected_counts["canonical_rows"]
            )
            run.add_check(
                source_file,
                "input_row_reconciliation",
                f"{expected_counts['raw_rows']} = "
                f"{expected_counts['rejected_rows']} rejected + "
                f"{expected_counts['exact_duplicates_removed']} duplicates + "
                f"{expected_counts['canonical_rows']} canonical",
                f"{raw_count} = {rejected_count} + {duplicate_count} + {len(clean_df)}",
                reconciliation_passes,
            )
            run.add_check(
                source_file,
                "canonical_key_uniqueness",
                "unique country/year keys",
                int(clean_df.duplicated(subset=manifest["key"]).sum()),
                not clean_df.duplicated(subset=manifest["key"]).any(),
            )
            domain_passes = (
                clean_df["continent"].isin(manifest["allowed_continents"]).all()
                and clean_df["year"].isin(manifest["allowed_years"]).all()
            )
            run.add_check(
                source_file,
                "canonical_domain_values",
                "allowed continents and years",
                "valid" if domain_passes else "invalid",
                bool(domain_passes),
            )
            run.add_audit(
                "recovery",
                source_file,
                "parse and map records",
                "manifest file layout and canonical column mapping",
                raw_count,
                raw_count,
            )
            run.add_audit(
                "validation",
                source_file,
                "quarantine invalid records",
                "manifest field validation rules",
                raw_count,
                raw_count - rejected_count,
            )
            run.add_audit(
                "deduplication",
                source_file,
                "remove exact duplicates",
                "retain first exact row; conflicting keys stop processing",
                raw_count - rejected_count,
                len(clean_df),
            )
            if not reconciliation_passes or not domain_passes:
                raise PipelineCheckError(
                    pd.DataFrame(validation_rows, columns=REPORT_COLUMNS)
                )

        if len(cleaned_by_source) != 4:
            raise ValueError(
                f"Expected four input formats, loaded {len(cleaned_by_source)}."
            )

        reference_filename = next(iter(cleaned_by_source))
        canonical_df = cleaned_by_source[reference_filename]
        for source_file, recovered_df in cleaned_by_source.items():
            if source_file == reference_filename:
                continue
            comparison = compare_canonical_export(
                canonical_df,
                recovered_df,
                manifest,
                source_file,
            )
            _append_comparison_report(run, comparison)
            run.add_audit(
                "agreement",
                source_file,
                "compare canonical records by key",
                "exact keys/text/integers; float atol=1e-8, rtol=0",
                len(canonical_df),
                len(recovered_df),
            )
            if not comparison["pass"].all():
                raise PipelineCheckError(
                    pd.DataFrame(validation_rows, columns=REPORT_COLUMNS)
                )

        _analysis_outputs(
            canonical_df, reporting_year, stager.staging_dir, manifest, run
        )
        if not all(bool(row["pass"]) for row in validation_rows):
            raise PipelineCheckError(
                pd.DataFrame(validation_rows, columns=REPORT_COLUMNS)
            )

        quarantine_all = pd.concat(quarantine_logs, ignore_index=True)
        duplicate_all = pd.concat(duplicate_logs, ignore_index=True)
        if list(quarantine_all.columns) != QUARANTINE_COLUMNS:
            quarantine_all = quarantine_all.reindex(columns=QUARANTINE_COLUMNS)
        if list(duplicate_all.columns) != DUPLICATE_COLUMNS:
            duplicate_all = duplicate_all.reindex(columns=DUPLICATE_COLUMNS)
        quarantine_all.to_csv(stager.staging_dir / "quarantine.csv", index=False)
        duplicate_all.to_csv(stager.staging_dir / "duplicate_log.csv", index=False)
        expected_per_file = manifest["expected_per_file"]
        expected_quarantine_total = (
            len(manifest["files"]) * expected_per_file["rejected_rows"]
        )
        expected_duplicate_total = (
            len(manifest["files"])
            * expected_per_file["exact_duplicates_removed"]
        )
        run.add_check(
            "",
            "total_quarantine_count",
            expected_quarantine_total,
            len(quarantine_all),
            len(quarantine_all) == expected_quarantine_total,
        )
        run.add_check(
            "",
            "total_duplicate_count",
            expected_duplicate_total,
            len(duplicate_all),
            len(duplicate_all) == expected_duplicate_total,
        )
        if (
            len(quarantine_all) != expected_quarantine_total
            or len(duplicate_all) != expected_duplicate_total
        ):
            raise PipelineCheckError(
                pd.DataFrame(validation_rows, columns=REPORT_COLUMNS)
            )

        export_canonical_formats(canonical_df, stager.staging_dir)
        round_trip_report = verify_canonical_round_trips(
            canonical_df, stager.staging_dir, manifest
        )
        _append_comparison_report(run, round_trip_report)
        for format_name in READERS:
            run.add_audit(
                "export_verification",
                f"canonical.{format_name}",
                "export, reload, and compare",
                "keys/text/integers exact; missingness exact; float atol=1e-8, rtol=0",
                len(canonical_df),
                len(canonical_df),
            )

        validation_report = pd.DataFrame(
            validation_rows, columns=REPORT_COLUMNS
        )
        if not validation_report["pass"].all():
            raise PipelineCheckError(validation_report)
        validation_report.to_csv(
            stager.staging_dir / "validation.csv", index=False
        )
        pd.DataFrame(audit_rows, columns=AUDIT_COLUMNS).to_csv(
            stager.staging_dir / "audit_log.csv", index=False
        )
        stager.publish()
        print(
            f"Processing complete: {len(canonical_df)} canonical rows; "
            f"outputs published to {output_dir}"
        )
        return 0

    except Exception as exc:
        print(f"Processing failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        if stager is not None:
            failed_report = _report_from_exception(exc, run)
            stager.preserve_failed_report(
                failed_report.to_csv(index=False),
                "validation_failed.csv",
            )
            pd.DataFrame(audit_rows, columns=AUDIT_COLUMNS).to_csv(
                stager.path_for("audit_log_failed.csv"), index=False
            )
            print(
                f"Failed validation report retained in {stager.staging_dir}",
                file=sys.stderr,
            )
        return 1
