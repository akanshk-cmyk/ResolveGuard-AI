# Pre-publication Security and Privacy Audit

Scope: working repository, curated `publication/ResolveGuard-AI` copy, its local Git history, Office files, notebooks, nested ZIPs, and the prepared upload ZIP. No GitHub access, upload or model API call was made. Secret values are deliberately absent from this report.

## Assessment

No confirmed live API credential was found in the prepared public files, included archives, or scanned local Git history. Two real local secrets were found only where expected: the private working `.env`. This does **not** establish universal absence of sensitive data. Actual privacy/portability cleanup candidates remain in source paths, archived logs and document metadata.

The previous GitHub-ready ZIP is a pre-audit snapshot. Its lack of exposed provider keys does not mean its metadata and paths are privacy-cleared. Review the findings below before releasing it. Original banking data and human-review evidence have not been edited to hide audit findings.

## Findings and actions

| ID | Severity/type | File and location | Finding | Action/status |
| --- | --- | --- | --- | --- |
| SEC-01 | High if disclosed; currently private | `.env:2`, `.env:10` | Actual Nebius key and local dashboard token; values not reproduced | Keep local. `.env` is ignored and absent from publication/archives/Git history. Private file unchanged. No evidence from this audit that those values were committed. |
| SEC-02 | Medium privacy | `tools/build_final_project_report.py:105` | Hardcoded user-home path to the local handout | Parameterize the optional authoring input or supply it as an explicit argument/environment value. It is not a runtime banking setting. The old path also exists inside `artifacts/refactor_20261101_01/source_checkpoint.zip`. Flagged, not rewritten. |
| SEC-03 | Medium privacy | `submission/ResolveGuard_AI_Final_Submission.zip!artifacts/remediation_20261101/tests_final.log:11` | Archived test log contains a user-home path | Excluding loose logs does not sanitize ZIP members. Publish a clearly labeled sanitized package/derivative or omit the archived log; preserve the original locally and document new hashes. Flagged. |
| SEC-04 | Low metadata privacy | `artifacts/human_review_received/817cb87ce51af0d4/Received_Human_Review.xlsx!docProps/core.xml` (`lastModifiedBy`) | Nonempty editor identity metadata | Review/remove metadata from a labeled public derivative. Keep the original workbook and source hash unchanged. A copy also exists in the submission ZIP. No author value is printed here. |
| SEC-05 | Low metadata privacy | Root PRD and BRD PDFs (`/Author`, XMP creator) | Nonempty author/creator fields require review | Verify attribution is intentional or export metadata-clean public derivatives. Text OCR does not inspect hidden metadata; these fields were checked separately. |
| SEC-06 | Low portability / workspace disclosure | `docs/OBSERVABILITY_RUNBOOK.md:38`; `artifacts/bow_workbook_inspection.json:2`; `artifacts/bow_workbook_inspection_latest.json:2`; baseline/final refactor check JSON command arguments; `artifacts/uv_migration/*`; `submission/final_project_summary/PDF_RENDER.json:3` | Absolute workspace/output paths remain in documentation and evidence | Prefer repository-relative instructions and sanitized public summaries. Do not rewrite original historical outputs or hashes. Archived versions may retain the same paths. |
| SEC-07 | Low portability; not a credential | `tools/build_final_project_report.py:18`; `resolveguard_demo_baseline/draw_architecture.py:16`; `draw_plain_language_flow.py:16` | Windows font paths in optional report/drawing utilities | Use portable font discovery when maintaining those tools. This does not expose an internal service or affect normal app execution. |
| SEC-08 | Informational | `tests/test_nebius_adapter.py:18,28,43`; `tests/test_review_and_integration.py:75`; `tests/test_reviewer.py:53-58` | Dummy provider keys and a test-only export passphrase | Verified test context, not production credentials. Retain meaningful security tests; do not replace fixtures with real secrets. |
| SEC-09 | Informational | `main.py`, `.replit`, UI/docs/test localhost references | Loopback addresses and explicit bind addresses | Intentional `127.0.0.1` local services and `0.0.0.0` Replit binding are not leaked internal hosts. No actual internal database URI or private-network service endpoint was identified. Preserve safe localhost defaults. |
| SEC-10 | Informational | Synthetic fixtures, test emails/card-redaction inputs and saved traces | Fictional identity data and test numbers | No genuine customer/company confidential records were established in reviewed content. Candidate card numbers resolved to six synthetic redaction-test inputs, 15 decimal metrics and five UUID false positives. Example-domain and GitHub noreply contacts are not real customer-email findings. |

Company names used as research references, bank-isolation tests, or the fictional Bank of Whatever are not automatically confidential company data. Regex matches alone do not establish a live credential, real person or private server.

## What was checked

- Read 1,671 workspace/publication files in the baseline scan, including the selected upload ZIP; inspected 4,278 file/archive-member occurrences and 1,767 Office/archive XML documents. Duplicate content was analyzed once and findings mapped to aliases.
- Checked common OpenAI/Anthropic, Groq, Pinecone, Perplexity, LangSmith, GitHub and AWS credential patterns; literal password/token assignments; JWT/private-key markers; exact local secret values in memory; database URIs; paths/IPs; email and personal-identifier candidates.
- Inspected the public copy's one local commit and 682 unique Git blobs for known local key values, including nested archive contents. No match; no remote repository/history was queried. The configuration changes from this audit remain local working changes, not a new published commit.
- Completed offline OCR on **25 unique PDF/image files, covering 58 pages/images**, with zero OCR failures. Content hashes cover all 25 unique visual items encountered by the main scan, including copies in archives. No credential/path/email/IP pattern was detected in the OCR text. SVG and notebook text/output content were included in text scanning.
- Inventoried 3,464 local SQLite/checkpoint files by schema only; did not export customer rows or tokens. These are local/runtime or isolated evaluation state, excluded from publication. Browser profiles and credential stores were not exported or content-scanned.
- Inventoried/excluded 63,699 third-party/cache/Git-object files and 2,387 private browser-profile files. Git object content was separately checked through the local Git blob audit. This is not a third-party dependency/CVE audit or a cryptographic proof of no leakage.

Raw findings, OCR text and schema inventories stay in ignored `artifacts/security_audit_20261101_01/`. Reports contain locations, not secret values. OCR/pattern detection has limits; it is not a substitute for reviewing consent and provenance of any future real data.

## Template and ignore changes applied

`.env.example` now documents that the offline demo needs no credentials. It contains blank credential placeholders, reply mode `off`, optional public evaluator model names and disabled LangSmith flags. Removed misleading unused endpoint/model entries and optional settings that are not needed for the basic setup. No OpenAI, Groq or Pinecone key is requested because this app uses Nebius.

`.gitignore` already covered `.env`, `.env.*`, `.venv`, Python caches, SQLite3/checkpoints, logs and browser profiles. Added direnv/local venv folders, cloud/SSH/kube credential directories, private-key/container files, HAR/packet captures, additional SQLite suffixes, local-secret overrides, the nested publication directory, and private audit/publication working output. Golden JSON/CSV/XLSX files, policy fixtures and evaluation evidence are **not** blanket-ignored.

Both working and publication copies received the template/ignore updates. The private `.env`, application code, test fixtures, customer UI, golden labels and historical result files were not modified. Existing public Git history and the pre-audit ZIP were not rewritten; address the privacy candidates before calling that package final.

## Before public release

1. Decide whether document author fields and local username/workspace paths are intended public attribution. Otherwise create clearly labeled sanitized derivatives and update their manifests; retain original evidence privately.
2. Inspect nested archives as well as loose files after sanitization. A `.gitignore` rule does not remove already tracked content or archive members.
3. Stage only the audited publication copy, recheck tracked paths/history and regenerate its upload archive after cleanup. Do not use the older ZIP without reconciling these findings.
4. Preserve synthetic-only data and keep provider/cloud features off in CI. If any actual key is later found in a public commit, revoke/rotate it before history cleanup. No such public exposure was verified here.

## Verification after template/ignore updates

All 14 explicit ignore-rule checks passed, including `.env` exclusion and `.env.example`/golden-JSON inclusion. All six HTTP/schema/asset/configuration compatibility tests passed. Source syntax/scoped credential checks passed. The 450 pre-refactor protected evidence/data hashes still match. No application code, private `.env`, golden labels, historical evaluations, local Git history or upload ZIP was rewritten.
