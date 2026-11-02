ResolveGuard AI — Week 3 / Own Use Case / Spreadsheet Track

START HERE
1. Read Project_Summary_Report.pdf.
2. Open ResolveGuard_Week3_Evaluation.xlsx. Start Here explains the scope;
   Cases 40 has matched baseline/improved outputs, labels, scores and failures.
   Raw Runs 240 contains every repeat; Scoring Rubric defines the checks.
3. Evidence_Analysis.ipynb contains executed analysis of the saved results.
   It does not rerun the agent. The analysis uses only Python standard-library
   modules; no API credentials are needed.
4. evidence/ contains original saved results, local traces and the optional
   judge appendix. supporting_code/ is a current reference snapshot, not an
   exact recovered historical checkout.

INTERACTIVE VIEWER
In this extracted directory run:
  python -m http.server 8773 --bind 127.0.0.1
Then open http://127.0.0.1:8773. The viewer uses saved outputs, not model calls.
PDF and Excel can be read directly without starting a server.

IMPORTANT LIMITS
The paired experiment is mock-rules v0 versus v4 on 40 identical cases, repeated
three times. Journey pass rate: 80% -> 97.5%. This is NOT evidence of GLM model
improvement, production readiness or real bank cost/latency. RG-056 remains a
failure in this comparison. Human reference review and provenance are pending.

TO FINISH THE COURSE SUBMISSION
- Review proposed labels. Keep frozen evidence unchanged; add review annotations
  separately. Corrected expectations require a new matched baseline/improved run.
- Record the demonstration using Loom_Recording_Script.md and add the real URL.
- Upload the spreadsheet, PDF/report, relevant supporting files and actual video
  link to the course portal. No upload or Loom recording has been performed.

Package_Validation.json records packaging checks. MANIFEST_SHA256.json lists file
hashes. No .env files, API credentials or runtime banking databases are included.
