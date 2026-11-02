# Refactoring step 01: review-table rendering

Status: complete; waiting for review before the next module.

The two review exporters now delegate table rendering to `tools/shared/report_rendering.py`. Their existing `table(rows)` wrappers remain. The original exporter keeps its "No records" empty state; the BOW exporter keeps its empty HTML table. Standalone script import support is verified in isolated Python processes.

Before extraction, 159 application tests and 13 fixture tests passed, with one application test skipped. Five new characterisation tests passed against the original functions before extraction. After extraction, 164 application tests and 13 fixture tests passed, with the same one skipped: 177 passed in total.

All 46 captured table outputs match exactly in UTF-8. HTML escaping, Unicode, nested JSON, column order, false/zero/null values and existing signatures are preserved. All other existing exporter functions and main blocks compare identically as Python ASTs. CSV handling, privacy filtering, source-data selection and archive generation were not altered.

Application code, API contracts, data models, UI files, source workbooks and live databases were not edited. Existing review packs were not regenerated. Tests used temporary storage.

- `changes.patch`: the two exporter diffs and all new helper/test files.
- `verification.json`: observed before/after results.
- `output_comparison.json`: exact output and signature comparison results.
- `baseline_tables.json`: original captured outputs.
- `build_review_pack.before.py` and `build_bow_review.before.py`: original exporter file bytes for rollback/reference.

Next proposed step: extract shared low-level XLSX reading while retaining the distinct formula and validation policies. No next-step changes have been made.
