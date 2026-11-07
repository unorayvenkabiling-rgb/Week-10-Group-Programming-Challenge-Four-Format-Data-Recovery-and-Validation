Week-10-Group-Programming-Challenge-Four-Format-Data-Recovery-and-Validation

Four-format data recovery and validation pipeline for CSV, Excel, JSON, and
Parquet inputs. The supplied files in `data/` are read as-is and are not
modified by the pipeline.

Setup and run

Install the Python dependencies:

```shell
py -m pip install -r requirements.txt
```

Run the pipeline from the repository root:

```shell
py main.py --config config.json
```

The configuration selects the input files, manifest, reporting year, and
output directory. Paths are resolved relative to the configuration file unless
they are absolute. By default, generated files are written to `outputs/`, which
is excluded from Git.

The pipeline loads and validates the input formats, reconciles the recovered
records, runs the analyses and export round-trip checks, then publishes outputs
only after all checks pass. Outputs include canonical CSV, Excel, JSON, and
Parquet data; analysis tables; quarantine and duplicate logs; and validation
and audit reports. Validation checks are also printed in the terminal for
successful and failed processing runs.

If processing fails, the command exits nonzero and leaves previously published
outputs unchanged. Failure reports are retained under `.outputs.staging/`.

Run the automated tests with:

```shell
py -m unittest discover -v
```

To execute the reporting notebook and regenerate its HTML export:

```shell
py -m jupyter nbconvert --to html --execute --inplace report.ipynb --output report.html
```

## Member roles and Git identities

| Member | GitHub identity | Commit email | Responsibility |
|---|---|---|---|
| Member 1 — Uno Timothy Rayven Kabiling | `@unorayvenkabiling-rgb` | `unorayven.kabiling@ust.edu.ph` | CSV and Excel readers |
| Member 2 — Carlos Gabriel Roman | `@gabroman28` | `carlosgabriel.roman@ust.edu.ph` | JSON and Parquet readers |
| Member 3 — Isaiah Collado | `@IsaiahCollado` | `isaiah.collado@ust.edu.ph` | Validation, quarantine, duplicates, and conflicts |
| Member 4 — John Christian Ballesteros | `@John-Christian-Ballesteros` | `johnchristian.ballesteros@ust.edu.ph` | Pandas analysis and NumPy matrix |
| Member 5 — Jeremiah Daniel Padilla | `@jdpadilla2` | `jeremiahdaniel.padilla@ust.edu.ph` | CLI, pipeline integration, staging, exports, and failure tests |
