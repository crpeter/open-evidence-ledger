# Methodology

## Purpose

The ledger makes narrowly framed, reproducible source claims available to people and retrieval systems. Inclusion is not endorsement, and omission is not a judgment about importance. The project does not independently decide criminal or state responsibility.

## Source selection

Sources are prioritized in this order: (1) ICJ; (2) ICC; (3) UN bodies, OHCHR, commissions of inquiry, and special procedures; (4) other courts and official investigations; (5) ICRC; (6) reputable human-rights organizations; and (7) high-quality investigative journalism. A lower-tier source may be necessary for a fact unavailable in a higher tier. Social-media material is used only when it is itself authenticated primary evidence.

## Record construction

1. Read the underlying document, not only reporting about it.
2. Draft one bounded `claim` that the cited page or paragraphs support.
3. Record who made the determination and the procedural posture.
4. Use the most conservative controlled `legal_status` that fits.
5. Add a short quotation only when it improves precision; otherwise use `null`.
6. Explain limitations, scope, and checks in `verification_notes`.
7. Link related records without implying equivalence.
8. Have a reviewer reproduce the claim from the citation before merge.

Facts within a source's recitation of party submissions are not recorded as that institution's findings. Report publication dates are not substituted for event dates. Where a source addresses a period rather than one event, `event_date` is `null` and the period is stated in the claim or notes.

## Controlled legal status

| Value | Meaning in this corpus |
| --- | --- |
| `ALLEGATION` | A non-court source attributes an allegation; it has not adopted it as a finding. |
| `DOCUMENTED_EVIDENCE` | The source documents evidence without making the stronger legal finding asserted by another actor. |
| `UN_FINDING` | A named UN investigative or expert body states a factual or legal finding. It is not a court judgment. |
| `COURT_ALLEGATION` | A prosecutor or court process states allegations or a threshold such as reasonable grounds; there is no conviction/final merits ruling. |
| `COURT_INTERIM_FINDING` | A court makes a provisional or interlocutory determination, not a final merits ruling. |
| `COURT_FINAL_FINDING` | A court has completed the relevant merits or advisory disposition. The record must say whether it is a judgment or a non-binding advisory opinion and must preserve any appeal posture. |
| `DISPUTED` | Reliable sources materially conflict and the record specifically identifies the dispute. |
| `UNKNOWN` | Available material does not support a more precise status. |

The status belongs to the exact claim, not the broader event. It may change only through a reviewed update citing the later procedural development; prior wording and provenance remain recoverable in Git history.

## Dates, actors, and language

Dates use ISO 8601. `publication_date` is mandatory for this corpus; if a genuinely undated source is ever accepted, the schema and policy must first be revised transparently rather than inserting an estimated date. Actor names describe attribution in the source. Summaries use attributed language (for example, “the Commission found”) and avoid converting “reasonable grounds,” “plausible rights,” or provisional measures into final conclusions.

## Verification and duplicate control

`schema/record.schema.json` is the authoritative per-record contract. The validator loads it with a Draft 2020-12 implementation and format checker, so required fields, unknown fields, types, enums, patterns, lengths, array constraints, and date/URI formats are not reimplemented in Python. Cross-record checks additionally enforce unique IDs, related-record integrity, filenames, consistent metadata for each `source_document_id`, and unique normalized claims within a document. Reuse of one source document across distinct claims remains legitimate.

Link checking is separate from corpus validation because official sites can be temporarily unavailable or block automated requests. A failed live request requires manual review; it does not prove that a citation is invalid.

## Corrections and uncertainty

Corrections are evidence, not politics: identify the record, exact disputed text, replacement, and source location. When scope, translation, attribution, or legal posture remains uncertain, record less, select the more conservative status, and state the uncertainty. Never fill a field by inference merely to make a record appear complete.
