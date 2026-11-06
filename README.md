# Four-Format Data Recovery and Validation

Run the recovery pipeline from the repository root with:

```powershell
py main.py --config config.json
```

The configuration selects the input files, manifest, reporting year, and output
directory. Paths are resolved relative to the configuration file (except
absolute paths). The default run writes its outputs to `outputs`.

The pipeline validates and reconciles each input, compares the four recovered
datasets, runs the analyses and export round-trip checks, and publishes output
files only after all checks pass. Successful outputs include the canonical data
in CSV, Excel, JSON, and Parquet formats; the analysis tables; quarantine and
duplicate logs; and `validation.csv` and `audit_log.csv`.

If processing fails, the command exits nonzero, leaves any previously published
outputs unchanged, and retains `validation_failed.csv` and
`audit_log_failed.csv` under `.outputs.staging`.
