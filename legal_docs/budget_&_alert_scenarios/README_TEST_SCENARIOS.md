# Legal Invoice Platform – Comprehensive Budget Test Pack (V2)

This version deliberately uses MULTIPLE DIFFERENT LAW FIRMS. The same firm is repeated only where repetition is necessary to test that a new invoice correctly reuses an existing budget.

DEFAULTS
- Default budget: $100,000
- Default alert threshold: 80%

FIRM DISTRIBUTION
1. NORTHSTAR LEGAL GROUP LLP
2. VERTEX LAW PARTNERS LLP
3. APEX LEGAL ASSOCIATES
4. HARBOR & CO. LEGAL
5. SUMMIT CORPORATE LAW LLP
6. RIVERSTONE LEGAL COUNSEL

IMPORTANT IDENTITY RULE
A budget is identified by Firm + Matter.
Matter matching should use Matter ID as the stable key when matter text varies.
The same Matter ID/name under a DIFFERENT firm must remain a separate budget.

RECOMMENDED TEST ORDER

A. NORTHSTAR – COMPLETE BUDGET LIFECYCLE
01 -> 02 -> 03 -> 04 -> 05 -> 06 -> 07

Expected:
01: $20,000 / $100,000 = 20%
02: $50,000 / $100,000 = 50%
03: $79,000 / $100,000 = 79%
04: $82,000 / $100,000 = 82% -> THRESHOLD ALERT
05: $97,000 / $100,000 = 97% -> HIGH UTILIZATION
06: $105,000 / $100,000 = 105% -> OVER BUDGET
07: $110,000 total. Same MAT-2088 despite matter-name variation.

Then adjust the NORTHSTAR MAT-2088 budget:
- Increase: +$25,000
- Old budget: $100,000
- New budget: $125,000
- Example reason: Additional litigation work approved due to expanded discovery scope.
- Confirm the action.

Then upload 08:
Expected total spend = $120,000 against adjusted $125,000.

09:
Same NORTHSTAR firm and same matter name, but MAT-2099.
Expected: separate new budget.

B. VERTEX
10:
New firm + MAT-7001. Same matter name as Northstar, but separate budget.

11:
Same Vertex MAT-7001.
Expected cumulative spend = $80,000 = exactly 80% threshold.

12:
Same Vertex firm, different MAT-7002.
Expected: separate budget.

C. APEX
13:
$120,000 invoice.
Expected: immediate over-budget after default $100,000 budget is created.

14:
Different APEX matter, normal under-budget case.

D. HARBOR
15 -> 16:
$60,000 then $25,000 = 85%.
Expected: threshold alert.

Optional adjustment test before 17:
Try increasing or decreasing the budget with a reason and confirmation.
Example increase: +$20,000.
Then upload 17 and verify the adjusted budget is used.

E. SUMMIT
18:
Same MAT-2088 ID/name as Northstar, but SUMMIT is a different firm.
Expected: separate budget.

19:
Exact duplicate invoice number of 18.
Expected: duplicate detection and NO double budget consumption.

F. RIVERSTONE
20:
Multiple timekeepers/roles/line items plus expenses.
Expected: correct extraction and total budget consumption.

21:
Matter ID intentionally missing.
Expected: manual Matter No. override flow.

22:
Firm intentionally missing.
Expected: validation/error path; no incorrect budget should be created.

23:
Zero amount.
Expected: validation or zero-impact behavior; it must not incorrectly consume budget.

AUDIT LOG CHECKLIST
For relevant rows, verify:
- action/event type
- firm
- matter ID
- matter name
- invoice number where applicable
- old budget
- adjustment amount
- new budget
- reason
- confirmation/action actor
- timestamp
- threshold/over-budget state where applicable
