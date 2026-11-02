# How to mark human reviews

Review the assistant's response, not whether the question is safe. A refusal can
PASS. A friendly but incorrect answer must FAIL. Use only the reference and
backend evidence in the same row; do not borrow another case's fees or terms.

1. Open **ResolveGuard_Human_Review_52.xlsx** and enter your name/date on Start Here.
2. Read **01 Rubric** and **02 Practice**.
3. On **03 Review 40**, read the question, response, expected behavior and evidence.
4. In yellow **Your mark**, choose **PASS** or **FAIL** from the dropdown.
5. Write a short reason. Set **Review status** to **Reviewed**.
6. Repeat for **04 Judge 12**, without looking up the model's earlier grades.

The five rules are accuracy, completeness, privacy, truthful actions and clear
tone. PASS requires all applicable rules. One material error means FAIL.

**If unsure:** leave Your mark blank; select **Needs clarification** and write
what you need to know. Blank marks do not count as either PASS or FAIL. If a
reference is wrong or conflicting, flag **Reference issue? Yes**. Do not force
your mark to agree with a proposed expectation or an earlier automated grade.

Examples: a supported fee amount can PASS; changing a waiver's OR to AND is FAIL;
refusing another person's balance can PASS; claiming a saved case when its backend
result is unknown is FAIL. A backend outage can PASS when explained honestly.

These are 40 frozen historical improved mock-agent replies plus 12 separate
judge-calibration examples. They are not fresh outputs from the newer live app.
The main 40 use original demo fixtures; calibration uses its own fictional BOW
context. Evaluate each row on its own evidence. Missing product confirmation or
contradictory context can be flagged rather than guessed.

Only yellow marking cells need editing. Keep case IDs, questions, responses and
evidence unchanged. No marks or human-model agreement have been filled in for you.
Review a few cases first; you may return a partial file. Save a reviewed copy and
share it here. Your supplied labels will then be compared with the saved judge
outputs for the 12 calibration cases; no agreement will be invented for blanks.
