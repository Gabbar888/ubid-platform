# Theme 1
## Unified Business Identifier (UBID) and Active Business Intelligence by Karnataka Commerce & Industry

### Context

Karnataka's business-facing regulatory landscape is served by 40+ State department systems — Shop Establishment, Factories, Labour, Karnataka State Pollution Control Board (KSPCB), BESCOM and other ESCOMs, BWSSB, Fire, Food Safety, urban and rural local bodies, and sector-specific regulators. Each of these systems was built in isolation, with its own schema, its own record identifiers and its own validation rules. Business name and address are stored as free text with no cross-system normalisation. Central Government anchors such as PAN and GSTIN exist, but are only partially captured in State systems.As a result, there is no reliable join key across the State's business data. The same business exists as different records in different databases, and master data cannot be linked. Activity data — inspections, renewals, consumption, compliance events — sits inside each department system and cannot be aggregated per business. Karnataka Commerce & Industries therefore cannot answer basic questions about its own industrial base: how many businesses are actually operating, in what sectors, where, and with what recent activity.Any working solution must sit alongside the existing systems. Source department systems cannot be modified, and a big-bang migration to a unified database is not realistic at this scale.

 

### The Problem

This problem has two parts. The second is only solvable after the first, which is why they are a single problem statement.

#### Part A — Give every business a Unique Business Identifier (UBID)

Given master data from 3–4 State department systems, automatically link records that refer to the same real-world business across those systems, and assign each business a single Unique Business Identifier.
Where PAN or GSTIN is present, the UBID should be anchored to that Central identifier. Where it is absent, the UBID stays an internally generated identifier that can be anchored later.
Every linkage decision must carry an explainable confidence signal. High-confidence matches can be committed automatically. Ambiguous matches must be routed to a human reviewer instead of being silently merged. Low-confidence records must stay separate until a reviewer decides.
Reviewer decisions must be captured in a way that can improve the linking over time.

#### Part B — Tell whether each business is actually active

Given a one-way stream of transaction and activity events from department systems (inspections, renewals, compliance filings, consumption data and similar signals), infer for each UBID whether the business is currently Active, Dormant or Closed.
Every classification must be explainable: a reviewer must be able to see which signals drove the verdict and over what time window.
Events that cannot be confidently joined to a UBID must be surfaced for review, not silently dropped.
 

### Non-Negotiables

Source department systems cannot be modified, re-platformed or migrated.
Real business data will not be released. Any Round 2 implementation will run on deterministically scrambled or synthetic data inside a sandbox.
Every automated decision — both linkages and activity classifications — must be explainable and reversible. A wrong merge is more costly than a missed one.
Hosted-LLM calls on raw PII are not permitted. Any LLM usage must work on scrambled or synthetic inputs only.
 

### What Success Looks Like

A working solution should eventually make the following behaviours possible:

A lookup by any department's record identifier, or by PAN / GSTIN, or by a combination of name, address and pin code, returns a single UBID with the evidence that supports that linkage.
Each UBID carries a current Active, Dormant or Closed status along with the events that justify it.
Ambiguous matches show up in a reviewer workflow rather than being silently committed, and reviewer decisions visibly influence subsequent behaviour.
Karnataka Commerce & Industries can run queries that are impossible today, such as: "active factories in pin code 560058 with no inspection in the last 18 months".
 

### Sample Scenario

To help you visualise the problem, consider a representative scenario:Master data for 2 pin codes in Bengaluru Urban, across 4 department systems (for example Shop Establishment, Factories, Labour and KSPCB), plus a one-way stream of transaction and activity events for the same businesses over the preceding 12 months.A good solution would link the records into a smaller set of UBIDs than input rows, auto-link high-confidence cases, send ambiguous ones to a reviewer, and anchor UBIDs to PAN or GSTIN wherever present. Activity events would then be joined to UBIDs and each business classified Active, Dormant or Closed with an evidence timeline. Karnataka Commerce & Industries should be able to run the "active factories without recent inspection" query against this data and get a real answer, with the underlying evidence.

 

### What Your Solution Should Cover

Round 1 of this hackathon is a written solution submission. Your solution document should make clear how you would build this platform. At minimum, it should cover:

Your understanding of the problem and the real-world constraints, in your own words.
Your approach to linking the same business across systems — how you handle varying name and address formats, missing or partial PAN / GSTIN, intra-department duplicates, and legacy data quality issues.
How you produce and calibrate the confidence signal for each linkage, and how you decide the auto-link, review and reject thresholds.
How the human-in-the-loop review is designed, and how reviewer decisions feed back into the system over time.
Your approach to inferring Active / Dormant / Closed status from heterogeneous event streams, and how the verdict stays explainable.
How you respect the non-negotiables above — particularly the "no source system changes" constraint and the requirement to work on scrambled or synthetic data.
A clear architecture overview, the key technology and model choices you would make, and the reasons behind them.
The main risks and trade-offs you see, and how you would handle them.
A rough implementation plan for Round 2, assuming a sandbox with representative data and APIs is provided.
 

### How We Will Evaluate Proposals

Clarity of problem understanding — does the team show they have grasped the real-world constraints, not just the surface problem?
Technical soundness of the proposed approach, including the treatment of entity resolution, confidence calibration and activity inference.
Feasibility within the non-negotiables, particularly the "no source system changes" and "scrambled-data" constraints.
Depth of thinking on edge cases, failure modes, explainability and reviewer workflow.
Quality of the architecture, the justification of technology and model choices, and the identified risks and trade-offs.
