Peer Code Reviews

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
