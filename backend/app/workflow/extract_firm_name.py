raw_text = "NORTHSTAR LEGAL GROUP LLP\n88 Market Street, Suite 700\nInvoice\nInvoice No: NS-2026-0147\nInvoice Date: 2026-08-08\nMatter: MAT-2088 - Orion Systems v. Delta Labs\nBilling Period: 2026-07-01 to 2026-07-31\nTimekeeper\nRole\nDate\nHours\nRate\nAmount\nM. Carter\nPartner\n2026-07-02\n5\n475.00\n2,375.00\nS. Rao\nAssociate\n2026-07-08\n8\n285.00\n2,280.00\nK. Wilson\nParalegal\n2026-07-14\n4.5\n165.00\n742.50\nExpenses\nCourt Filing\n225.00\nCourier\n60.00\nSubtotal:\n5,682.50\nTax:\n0.00\nTotal:\n$5,682.50\n"

import re

firm_match = re.search(r"\b([A-Z][a-zA-C-z0-9'&.\- ]+?\b(?:L\.?L\.?P\.?|P\.?C\.?|L\.?L\.?C\.?|P\.?L\.?L\.?C\.?|Inc\.?|Ltd\.?|Law\s+Offices?|Legal\s+Group|Law\s+Group|Attorneys\s+at\s+Law))\b", raw_text, re.IGNORECASE)

firm_name= firm_match.group(1).strip() if firm_match else None
print(firm_name)