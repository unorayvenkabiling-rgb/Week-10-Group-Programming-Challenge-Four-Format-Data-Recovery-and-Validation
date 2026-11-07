Peer Code Reviews
Peer Review 1: Member 1 Codebase
Reviewer: Carlos Gabriel Roman (Member 2)
Target Author: Uno Kabiling (Member 1)
Target Branch / PR: member-1
Files Reviewed: src/readers.py
Review Status: Changes Requested

Code Overview
Member 1 implemented the initial data ingestion loaders for the CSV (read_csv_file) and Excel (read_excel_file) file formats. The implementation successfully targets the correct Excel "observations" sheet and correctly handles the CSV cp1252 encoding, semicolon delimiters, and skipped comment lines.

Detailed Findings & Line-by-Line Feedback

src/readers.py
Lines 8 & 16 (Missing Function Signatures & Type Hints):
Issue: Functions lack parameters and return annotations (-> pd.DataFrame), and instead rely on a globally loaded config.json file. This violates the rubric requirement for parameterized functions.
Recommendation: Update function signatures to accept filepath: str and manifest: dict dynamically from the main pipeline.

Lines 10 & 18 (Missing Schema Normalization):
Issue: The code returns raw DataFrames directly from pd.read_csv and pd.read_excel. It fails to map the columns to the canonical names or drop the extra CSV metadata column.
Recommendation: Extract source_to_canonical from the manifest dictionary, use .rename(columns=...), and filter the returned DataFrame against manifest.get("canonical_order", []).

Lines 12-14 & 20-22 (Anti-Pattern Exception Handling):
Issue: Wrapping the file readers in a try-except block and returning None violates the rubric's failure handling rules. Returning None causes downstream crashes rather than safely stopping the program.
Recommendation: Remove the try-except Exception: blocks completely. Allow FileNotFoundError to raise naturally so the pipeline halts safely on missing files.

Conclusion & Next Steps
Member 1 nailed the format-specific arguments for pandas. Once the function signatures are updated with parameters, the raw columns are mapped to the canonical schema, and the silent error catching is removed, these readers will be ready to merge into main.


Peer Review 2: Member 2 Codebase
Reviewer: Isaiah Collado (Member 3)
Target Author: Member 2
Target Branch / PR: `member-2`
Files Reviewed: `src/json_parquet_loaders.py`, `tests/test_member2.py`
Review Status: Changes Requested

1. Code Overview
Member 2 implemented data loaders for JSON (`load_json_records`) and Parquet (`load_parquet_records`) file formats, as well as a corresponding unit test suite in `tests/test_member2.py`.

2. Detailed Findings & Line-by-Line Feedback

`src/json_parquet_loaders.py`
Lines 10 & 33 (Manifest Dictionary Access):
Issue: Code uses `manifest.get("files", {}).get(...)`. In `manifest.json`, `"files"` is a JSON array (list of objects), not a top-level dictionary. Calling `.get()` directly on a list causes an `AttributeError`.
  * *Recommendation:* Use a list comprehension or generator to locate the matching format entry

Lines 18 & 42 (Canonical Order Extraction):
Issue: The loader originally attempted to read `manifest["schema"]["canonical_columns"]`. The manifest defines column ordering under top-level `canonical_order`.
Recommendation: Extract column ordering directly via `manifest.get("canonical_order", [])`.

Lines 19 & 43 (Missing Column Schema Protection):
Issue: Indexing `df[canonical_order]` directly without validation crashes on missing columns (e.g., `missing_column.csv`).
Recommendation: Validate column presence before reordering, raising a descriptive `KeyError` if any canonical columns are missing.

Line 21 (`pd.to_numeric` Usage):
Issue: `errors='ignore'` is deprecated in newer Pandas versions and can lead to silent type conversion failures.
Recommendation: Explicitly check data types or use clean string stripping before numeric type conversion.

Line 36 (File Handling Safety):
Issue:* JSON loading opened files without explicit UTF-8 encoding or corrupted file catching.
Recommendation: Pass `encoding='utf-8'` inside `open()` and wrap `json.load()` in a `try-except json.JSONDecodeError` block to catch malformed inputs.

`tests/test_member2.py`
`setUp()` Initialization:
Issue: Referencing non-existent manifest keys caused all test cases to fail during test setup.
Recommendation: Updated `self.canonical_columns` to read `self.manifest.get("canonical_order", [])`.

Test Coverage:
Feedback: Added positive assertions for record counts (`len(df) == 1712`) and added negative test cases (`test_missing_column_rejection`, `test_unparseable_json_rejection`).
Line 31 (`bad_manifest` structure):**
Issue: Mock manifest in `test_missing_column_rejection` omitted the `"files"` list, causing loader lookups to fail before testing schema rejection.
Recommendation: Include a dummy `"files"` array inside `bad_manifest`.

3. Conclusion & Next Steps
Once the list lookups for `manifest["files"]` and mock manifest structures are updated, the loader functions will safely parse JSON/Parquet datasets into canonical format for downstream row validation and quarantine processing.

Peer Review 3: Member 3 Codebase
Reviewer: John Christian Ballesteros (Member 4)
Target Author: Isaiah Collado (Member 3)
Target Branch / PR: `member-3`
Files Reviewed: `validation.py`, `test_validation.py`
Review Status: Approved

1. Code Overview
Member 3 provides a robust source code supported by comprehensive unit tests.

2. Test Coverage
Handles errors and edge cases gracefully.

3. Conclusion & Next Steps
Member 3's code is clean. Its pull request is approved.

# Member review record

## Member 5 review of Member 4 analysis work

- Reviewed commit: `a2f34346a2e4a68965198c1583fa1bdd2fe79fb2` (`Add test analysis`)
- Reviewed change: Member 4's pandas/NumPy analysis implementation and tests.
- Feedback: The supplied control results and existing tests were sound, but
  coverage should include actual recovered data and the 1997 reporting-year
  configuration. Empty NumPy selections should fail explicitly rather than
  produce a misleading `NaN`; analysis should use `.loc` for selection and
  expose return types.
- Response: Updated the analysis implementation and expanded the tests in
  commit `2ed54f4` (`Fix and verify analysis functions`). The tests cover the
  recovered dataset, 2007 controls, 1997 reporting year, empty selection, and
  NumPy outputs.
