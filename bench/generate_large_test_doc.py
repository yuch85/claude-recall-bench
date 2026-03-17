#!/usr/bin/env python3
"""
Generate large test documents (up to 500K tokens) of unique legal clauses
for full-recall evaluation of large-context models like Claude (1M context).

Usage:
  python generate_large_test_doc.py --tokens 500000 --output test_docs/500k_legal.txt
  python generate_large_test_doc.py --tokens 100000 --output test_docs/100k_legal.txt
"""

import argparse
import hashlib
import os
import random


# Import clause generation from full_recall.py
# (duplicated here for standalone use)

CLAUSE_SUBJECTS = [
    "The Purchaser", "The Seller", "The Licensor", "The Licensee", "The Borrower",
    "The Lender", "The Guarantor", "The Tenant", "The Landlord", "The Employer",
    "The Contractor", "The Consultant", "The Service Provider", "The Client",
    "The Distributor", "The Supplier", "The Franchisor", "The Franchisee",
    "The Investor", "The Company", "The Agent", "The Principal", "The Trustee",
    "The Beneficiary", "The Insurer", "The Insured Party", "The Indemnifying Party",
    "The Indemnified Party", "The Disclosing Party", "The Receiving Party",
    "The Subcontractor", "The Assignee", "The Mortgagor", "The Mortgagee",
    "The Settlor", "The Executor", "The Administrator", "The Joint Venture Partner",
    "The Limited Partner", "The General Partner", "The Managing Member",
]

CLAUSE_OBLIGATIONS = [
    "shall use commercially reasonable efforts to",
    "covenants and agrees to",
    "undertakes to",
    "shall be obligated to",
    "hereby agrees to",
    "shall promptly",
    "shall at all times",
    "shall in good faith",
    "warrants that it will",
    "represents and warrants that it shall",
    "shall exercise due diligence to",
    "acknowledges its obligation to",
    "irrevocably agrees to",
    "unconditionally undertakes to",
    "shall take all necessary steps to",
    "is required to",
    "shall make every reasonable effort to",
    "commits to",
    "has the ongoing duty to",
    "shall diligently",
]

CLAUSE_ACTIONS = [
    "maintain adequate insurance coverage with a minimum limit of {amount} per occurrence and {amount2} in the aggregate for the duration of the Term, naming the other party as an additional insured on all applicable policies",
    "provide written notice of any material change in its financial condition within {days} business days of such change becoming known to it, including but not limited to any bankruptcy filing, insolvency proceeding, or change of control event",
    "deliver audited financial statements prepared in accordance with {standard} within {days} days following the end of each fiscal quarter, certified by an independent registered public accounting firm",
    "obtain all necessary governmental approvals, permits, and licenses required for the lawful conduct of the Business in the Territory of {territory}, and to maintain such approvals in full force and effect",
    "indemnify and hold harmless the other party from and against any and all claims, damages, losses, costs, and expenses (including reasonable attorneys' fees) arising out of or resulting from any breach of Section {section}",
    "refrain from soliciting, hiring, or engaging any employee, consultant, or contractor of the other party for a period of {months} months following the termination or expiration of this Agreement",
    "ensure that all Confidential Information is stored in accordance with industry-standard security protocols, including but not limited to {encryption} encryption at rest and in transit, with regular security audits conducted no less frequently than annually",
    "submit quarterly compliance reports detailing its adherence to the terms and conditions of Schedule {schedule} no later than the {ordinal} business day of each calendar quarter, in the form prescribed by the Compliance Committee",
    "remit all royalty payments due under Article {article} within {days} business days of the end of each reporting period, together with a detailed statement of Net Sales broken down by product line and geographic region",
    "establish and maintain a dedicated escrow account at a mutually agreed financial institution with an initial deposit of not less than {amount}, to be replenished whenever the balance falls below {amount2}",
    "conduct an independent third-party audit of its operations and financial records at least once every {months} months, at its own cost and expense, and make the complete and unredacted results available to the other party within {days} days of completion",
    "implement a comprehensive data protection program in compliance with all applicable privacy laws, including the General Data Protection Regulation (GDPR), the California Consumer Privacy Act (CCPA), and any successor legislation in effect in {territory}",
    "appoint a qualified representative with appropriate seniority and decision-making authority to serve as the primary point of contact for all matters arising under this Agreement, and to attend quarterly review meetings at {location}",
    "execute and deliver all documents, instruments, certificates, and agreements as may be reasonably requested by the other party to effectuate the transactions contemplated by Section {section} of this Agreement",
    "maintain accurate, complete, and up-to-date records of all transactions conducted under this Agreement for a minimum period of {years} years following the expiration or termination hereof, in a format that permits ready retrieval and audit",
    "provide technical support services in accordance with the service level agreement attached hereto as Exhibit {exhibit}, including guaranteed response times of no more than {hours} hours for Priority 1 critical issues and {days} business days for Priority 3 issues",
    "grant a non-exclusive, worldwide, royalty-free license to use, reproduce, and create derivative works of the Licensed Materials solely for internal business purposes within the scope defined in Appendix {appendix}, subject to the restrictions in Article {article}",
    "procure and maintain professional indemnity insurance and errors and omissions coverage with limits of not less than {amount} per claim and {amount2} in the aggregate, with an internationally recognized insurance carrier rated A- or better by AM Best",
    "comply with all applicable anti-corruption laws and regulations, including without limitation the United States Foreign Corrupt Practices Act, the United Kingdom Bribery Act 2010, and all local anti-bribery legislation in {territory}",
    "negotiate in good faith any amendments to the pricing schedule and fee structure set forth in Exhibit {exhibit} in the event of a material change in market conditions, currency fluctuations exceeding {rate}%, or regulatory changes as defined in Section {section}",
    "provide a detailed transition plan within {days} business days of receiving notice of termination, covering all aspects of knowledge transfer, data migration, and handover of ongoing deliverables to the successor provider",
    "establish and fund a reserve account in the amount of {amount} to cover potential warranty claims, product recalls, or service failures occurring within the warranty period specified in Section {section}",
    "make available to the other party, upon {days} business days' prior written notice, all books, records, contracts, and documents relating to the subject matter of this Agreement for inspection and copying during normal business hours at {location}",
    "participate in joint business reviews on a quarterly basis to assess performance against the key performance indicators set forth in Schedule {schedule}, and to develop corrective action plans for any areas of underperformance",
    "ensure that all personnel assigned to perform services under this Agreement have undergone appropriate background checks, possess relevant professional qualifications, and have completed training on data security and confidentiality requirements",
]

CLAUSE_CONDITIONS = [
    "provided, however, that this obligation shall not apply to any information that (i) is or becomes publicly available through no fault of the obligated party, (ii) was lawfully in the possession of the obligated party prior to disclosure, or (iii) is independently developed without reference to the Confidential Information",
    "subject to the limitations set forth in Section {section}, and in no event shall the aggregate liability of either party under this provision exceed {amount} in any consecutive twelve-month period",
    "notwithstanding the foregoing, this provision shall automatically terminate upon the earlier of (a) the {ordinal} anniversary of the Effective Date, or (b) the closing of a Qualified Public Offering as defined in Article {article}",
    "except to the extent that such disclosure is required by applicable law, regulation, subpoena, or order of any court or governmental authority having competent jurisdiction over the parties",
    "on the condition that the other party provides prior written consent, which consent shall not be unreasonably withheld, conditioned, delayed, or qualified for a period exceeding {days} business days from the date of request",
    "in accordance with the procedures and timelines set forth in Schedule {schedule}, as may be amended from time to time by mutual written agreement of the authorized representatives of both parties",
    "subject to force majeure events as defined in Article {article}, which shall toll any applicable deadlines and cure periods for the duration of such event plus {days} additional business days following cessation",
    "provided further that any failure to comply with this provision that is cured in all material respects within {days} calendar days of written notice thereof shall not constitute an event of default under this Agreement",
    "without prejudice to any other rights or remedies that the non-breaching party may have under this Agreement, at law, or in equity, whether arising before or after the date of any breach",
    "subject to the regulatory approvals and third-party consents listed in Schedule {schedule}, which the parties shall use their respective best efforts to obtain within {days} business days of the execution date",
]

CLAUSE_CONSEQUENCES = [
    "Any breach of this Section shall entitle the non-breaching party to seek injunctive relief, specific performance, and any other equitable remedies in addition to all remedies available at law, without the necessity of posting a bond, undertaking, or other security.",
    "In the event of a material breach that remains uncured for a period of {days} calendar days following delivery of written notice specifying the nature of such breach in reasonable detail, the non-breaching party may terminate this Agreement effective immediately and pursue all available remedies.",
    "The parties irrevocably agree that the obligations and restrictions set forth herein are reasonable and necessary for the protection of the legitimate business interests of both parties, and that any violation would cause irreparable harm not adequately compensable by monetary damages alone.",
    "Failure by either party to enforce any provision of this Section at any time shall not constitute a waiver of such provision or of the right to enforce such provision or any other provision at any subsequent time, nor shall any single or partial exercise of any right preclude further exercise thereof.",
    "The prevailing party in any legal action, arbitration, or other proceeding brought to enforce or interpret this provision shall be entitled to recover its reasonable attorneys' fees, court costs, expert witness fees, and all other reasonable expenses of litigation or arbitration.",
    "Any amounts not paid when due under this Section shall automatically bear interest at the lesser of (a) {rate}% per annum above the prime rate published by the Wall Street Journal or (b) the maximum rate permitted by applicable law, compounded monthly from the due date until paid in full.",
    "This obligation shall survive the expiration, termination, or rescission of this Agreement for a period of {years} years from the date of such expiration, termination, or rescission, regardless of the reason therefor or the party initiating such action.",
    "The parties acknowledge and agree that monetary damages would be an insufficient remedy for any breach or threatened breach of this provision and that the non-breaching party shall be entitled to equitable relief, including but not limited to temporary restraining orders, preliminary and permanent injunctions, and orders for specific performance, in addition to all other available remedies.",
]

AMOUNTS = [
    "$1,500,000", "$2,750,000", "$5,000,000", "$10,000,000", "$500,000",
    "$750,000", "$3,250,000", "$7,500,000", "$15,000,000", "$25,000,000",
    "$100,000", "$250,000", "$4,000,000", "$8,500,000", "$12,000,000",
    "$1,000,000", "$6,000,000", "$20,000,000", "$350,000", "$900,000",
    "$50,000,000", "$75,000,000", "$125,000", "$1,750,000", "$9,000,000",
]

TERRITORIES = [
    "the United States and Canada", "the European Economic Area",
    "England and Wales", "the Asia-Pacific region",
    "the State of New York", "the Commonwealth of Australia",
    "the Federal Republic of Germany", "the Republic of Singapore",
    "the People's Republic of China", "the United Kingdom",
    "the State of California", "the Province of Ontario",
    "the Kingdom of the Netherlands", "Japan and South Korea",
    "the United Arab Emirates", "the Republic of India",
    "the Swiss Confederation", "the Republic of France",
    "the Federative Republic of Brazil", "the State of Texas",
]

STANDARDS = [
    "Generally Accepted Accounting Principles (GAAP)",
    "International Financial Reporting Standards (IFRS)",
    "United Kingdom Generally Accepted Accounting Practice (UK GAAP)",
    "Australian Accounting Standards (AASB)",
    "the accounting standards mandated by the relevant regulatory authority",
]

ENCRYPTIONS = ["AES-256", "AES-128", "RSA-2048", "ChaCha20-Poly1305", "TLS 1.3"]
LOCATIONS = [
    "the principal offices of the Company in New York City",
    "a mutually agreed location in the City of London",
    "the registered office of the Purchaser in Singapore",
    "the headquarters of the Service Provider in San Francisco, California",
    "the offices of external counsel to the Seller in Frankfurt am Main",
    "a neutral venue in Hong Kong SAR",
    "the corporate headquarters in Toronto, Ontario",
    "the regional office in Dubai, United Arab Emirates",
]


def generate_unique_clause(rng: random.Random, clause_num: int) -> str:
    subject = rng.choice(CLAUSE_SUBJECTS)
    obligation = rng.choice(CLAUSE_OBLIGATIONS)
    action = rng.choice(CLAUSE_ACTIONS)
    condition = rng.choice(CLAUSE_CONDITIONS)
    consequence = rng.choice(CLAUSE_CONSEQUENCES)

    replacements = {
        "{amount}": rng.choice(AMOUNTS),
        "{amount2}": rng.choice(AMOUNTS),
        "{days}": str(rng.choice([5, 7, 10, 14, 15, 20, 21, 30, 45, 60, 90])),
        "{months}": str(rng.choice([6, 12, 18, 24, 36, 48])),
        "{years}": str(rng.choice([2, 3, 5, 7, 10, 15])),
        "{section}": f"{rng.randint(1, 30)}.{rng.randint(1, 15)}",
        "{article}": rng.choice(["II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII"]),
        "{schedule}": rng.choice(["A", "B", "C", "D", "E", "F", "G", "H"]),
        "{exhibit}": rng.choice(["A", "B", "C", "D", "E", "F", "G", "H", "J", "K"]),
        "{appendix}": rng.choice(["1", "2", "3", "4", "5", "A", "B", "C", "D"]),
        "{territory}": rng.choice(TERRITORIES),
        "{standard}": rng.choice(STANDARDS),
        "{encryption}": rng.choice(ENCRYPTIONS),
        "{location}": rng.choice(LOCATIONS),
        "{ordinal}": rng.choice(["first", "second", "third", "fourth", "fifth", "seventh", "tenth", "fifteenth"]),
        "{hours}": str(rng.choice([1, 2, 4, 8, 12, 24, 48])),
        "{rate}": str(rng.choice([3, 5, 8, 10, 12, 15, 18])),
    }

    for key, val in replacements.items():
        action = action.replace(key, val, 1)
        condition = condition.replace(key, val, 1)
        consequence = consequence.replace(key, val, 1)

    # Structured heading
    part = (clause_num // 20) + 1
    chapter = ((clause_num % 20) // 5) + 1
    section = (clause_num % 5) + 1
    heading = f"Part {part}, Chapter {chapter}, Section {chapter}.{section}"

    return f"{heading}. {subject} {obligation} {action}. {condition}. {consequence}"


def generate_document(target_tokens: int, seed: int = 42) -> tuple[str, str]:
    """Generate document and its SHA-256 hash."""
    rng = random.Random(seed)
    clauses = []
    current_tokens = 0
    clause_num = 0

    while current_tokens < target_tokens:
        clause = generate_unique_clause(rng, clause_num)
        clauses.append(clause)
        current_tokens += len(clause) // 4
        clause_num += 1

    document = "\n\n".join(clauses)
    doc_hash = hashlib.sha256(document.encode()).hexdigest()

    return document, doc_hash


def main():
    parser = argparse.ArgumentParser(description="Generate large test documents")
    parser.add_argument("--tokens", type=int, default=500000, help="Target token count")
    parser.add_argument("--output", default="test_docs/legal_doc.txt", help="Output file")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--hash-file", default=None, help="Write SHA-256 hash to this file (default: <output>.sha256)")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)

    print(f"Generating {args.tokens:,} token document (seed={args.seed})...")
    document, doc_hash = generate_document(args.tokens, args.seed)

    actual_tokens = len(document) // 4
    actual_chars = len(document)
    clause_count = document.count("Part ")

    with open(args.output, "w") as f:
        f.write(document)

    hash_file = args.hash_file or f"{args.output}.sha256"
    with open(hash_file, "w") as f:
        f.write(doc_hash)

    print(f"Generated: {args.output}")
    print(f"  Clauses: {clause_count}")
    print(f"  Characters: {actual_chars:,}")
    print(f"  Estimated tokens: {actual_tokens:,}")
    print(f"  SHA-256: {doc_hash}")
    print(f"  Hash file: {hash_file}")


if __name__ == "__main__":
    main()
