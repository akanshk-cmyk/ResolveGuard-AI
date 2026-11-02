ResolveGuard BOW Repository Export — November 1, 2026

Open ResolveGuard_BOW_Repository_Export.xlsx. The first tab explains the other
eleven tabs, when to use them, counts, source paths and cautions.

This export follows the active repository source pointer and validates Pydantic
schemas, relationships, source workbook/file hashes and chunk integrity before
writing. Every data cell was then read back and checked against the source.

All data is fictional. Policies and approvals are test-only. This package does
not contain real bank terms, live session credentials or runtime banking events.
It does not run evaluations, approve labels or alter the source workbooks.

The 12-tab export uses the repository's normalized dates and source fields.
Original_Source_Workbook.xlsx is a separate byte-identical copy with its original
archived sheets. Archived records are not merged into the active export.

json/ contains exact active source files. csv/ contains review-friendly copies.
Field_Dictionary.csv explains field types, meanings and examples.
Source_Manifest.json retains source version, row lineage and normalization notes.
Export_Validation.json records the cell-by-cell and hash checks.

The 100 golden rows are scenario definitions, not 100 fresh scored results.
NOT_RUN source values stay unchanged; actual execution reports are separate.
Runtime-created support cases, card locks and fraud tickets are not fixture rows
and are deliberately not mixed into this source-data review package.
