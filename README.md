# Four-Format Data Recovery and Validation

Run the recovery pipeline from the repository root with:

```powershell
py main.py --config config.json
```

The configuration selects the input files, manifest, reporting year, and output
directory. Paths are resolved relative to the configuration file (except
absolute paths). The default run writes its outputs to `outputs`.
Reusable orchestration is available from `src.pipeline`; `main.py` is the
command-line entry point.

The pipeline validates and reconciles each input, compares the four recovered
datasets, runs the analyses and export round-trip checks, and publishes output
files only after all checks pass. Successful outputs include the canonical data
in CSV, Excel, JSON, and Parquet formats; the analysis tables; quarantine and
duplicate logs; and `validation.csv` and `audit_log.csv`.

The round-trip verifier reads CSV fields as strings and explicitly converts
declared numeric columns. Excel and JSON readers infer numeric values, while
Parquet preserves stored types; the verifier normalizes every format to the
manifest schema before comparing values.

If processing fails, the command exits nonzero, leaves any previously published
outputs unchanged, and retains `validation_failed.csv` and
`audit_log_failed.csv` under `.outputs.staging`.

Run the automated checks with:

```powershell
py -m unittest discover -v
```

The required recovery and failure-category outcomes are recorded in
`test_results.txt`.

Install the application and notebook dependencies with:

```powershell
py -m pip install -r requirements.txt
```

Execute the reporting notebook and create its HTML export from the repository
root with:

```powershell
py -m jupyter nbconvert --to html --execute --inplace report.ipynb --output report.html
```

## Member ownership and Git identities

| Member | Responsibility | Git identity |
|---|---|---|
| Member 5 — jdpadilla2 | CLI and audit integration, output staging, canonical export/reload verification, and failure-category tests | `jdpadilla2 <jeremiahdaniel.padilla@ust.edu.ph>` |

Add the other members' assigned responsibilities and Git identities here for
the complete group record.
