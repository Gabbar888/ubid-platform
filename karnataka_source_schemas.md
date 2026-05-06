# Karnataka State Department Source Schemas — Research for UBID Prototype

**Purpose.** Identify and document the actual data schemas of representative Karnataka State department systems and central anchors so we can generate synthetic data that closely mirrors what the UBID platform will see in production. Every schema below is anchored to a primary source (statute, official portal, or published form) and a quality assessment for entity-resolution prototyping.

**How to use this document.** For each system, we list (a) the official portal / statute, (b) the canonical record fields with types and observed quirks, (c) the identifiers that appear there, and (d) where you can get real or representative data to seed synthetic generation. Use the Verification column at the end of each section to sanity-check any field before committing to it in the prototype schema.

---

## 1. e-Karmika — Karnataka Shop & Establishment (Department of Labour)

**System.** e-Karmika, the online portal for registration, renewal, amendment, and closure under the **Karnataka Shops and Commercial Establishments Act, 1961** and Rules 1963.

**Primary statute / form.** Form A is the combined application for registration / renewal / change of information (Rules 3, 3-A, 5). Form C is the issued Registration Certificate.

**Sources.**
- Portal: https://www.ekarmika.karnataka.gov.in/
- Form A PDF (canonical field list): https://www.datocms-assets.com/40521/1625469907-kar-se-form-a-combined-application-for-establishment-registration-renewal-change.pdf
- Form A summary at greythr (Rules 3/3-A/5): https://www.greythr.com/wiki/compliances/form-a-combined-application-for-registration-renewal-report-change-of-information-karnataka-s&e-act/

### 1.1 Canonical fields (verbatim from Form A)

The following are the actual labelled fields on the official Form A. Field names in italics are reproduced as they appear on the form.

**PART A — Establishment**

| # | Field | Notes |
|---|---|---|
| 1 | *Name of the establishment and postal address* | Single free-text block. Phone, fax, email captured separately under it. |
| 1A | *Name of the Head Office (if any) with postal address* | Optional; when present, links the establishment to a parent. |
| 2 | *Details of the Proprietor / Managing Partner / Director* | Repeating table: Sl.No, Name, Designation (working / non-working), Residential Address, Tel [O][R], Fax/Email. **Multi-row.** |
| 3 | *Details of Head of Unit / Authorised Signatory / Manager* | Same repeating-row structure as #2. |
| 4 | *Nature of Business* | Free text. Sector classification is **not** code-driven on the form — controlled-vocabulary mapping is the platform's responsibility. |
| 5 | *Date of commencement of Business* | Date. Used as the natural Nascent-state anchor. |
| 6 | *Names of members of employer's family employed in the establishment* | Repeating: Sl.No, Name, Relationship. Often blank. |
| 7 | *No. of employees* | Four counts: Male, Female, Young Persons, Total. |
| 8 | *Particulars of fees remitted* | Receipt/Challan number, Date, Amount. The fee receipt is the activity event we'd ingest. |
| 9 | *Notified weekly holiday* | Single field; rarely useful for resolution but auditable. |

**PART B — Renewal-only**

| Field | Notes |
|---|---|
| Renewal period (From / To) | Pre-2019 only had real meaning; post-2019 amendment made renewal automatic on self-cert + fee. |
| Original Registration Certificate No. | The persistent S&E identifier. |
| Ward No. and Date of issue / Circle | Geographic / jurisdictional identifier; useful as an address-component cross-check. |

**PART C — Change-of-information**

A repeating table: Sl.No, *Sl.No in Part A*, *Present description (previous declaration)*, *Description after change*, *Reasons for change*. This is **the change-data-capture surface** of e-Karmika — for entity-resolution drift analysis (address change, ownership change), Part C entries are the gold-mine event stream.

### 1.2 Identifiers exposed

| Identifier | Notes |
|---|---|
| Establishment Registration Number (Form C) | The S&E unique key. Format varies by jurisdiction / circle; not a fixed regex. |
| Ward / Circle code | Sub-jurisdictional, not unique alone. |
| PAN | Captured during online registration on the portal — required for new applicants. **Often present, but historically inconsistent.** |
| GSTIN | **Rare** in S&E records; not a mandatory field. |

### 1.3 Quirks that affect entity resolution

- The 2019 amendment (Notification dated 11.06.2019) abolished periodic renewal; post-2019, "renewal" is auto-triggered by self-certification + fee. This is the regime change called out in the proposal — a renewal event pre-2019 is a strong activity signal, post-2019 it is near-automatic. Cite this date in the activity-engine config.
- Names are bilingual: Kannada name board is **mandatory** under Rule 24-A. Records frequently carry both Kannada and Roman-script names; portal forms tend to capture the Roman version, but offline / KarnatakaOne-submitted forms may carry the Kannada original. Plan the transliteration step accordingly.
- Each branch requires separate registration. So one PAN can map to many establishment registration numbers. This is precisely the proprietorship + multi-branch hierarchy that the three-layer UBID model anchors to.
- Form A is the **only** schema; there is no separate registration / renewal / amendment form — Parts A/B/C are appended as needed. Synthetic generation should reuse the single record skeleton and toggle Part B / Part C presence.

### 1.4 Data availability for prototyping

- **Schema confidence: HIGH.** Form A is the legally prescribed schema; field names and structure are verbatim from the official PDF.
- **Real-data availability: LOW.** e-Karmika does not publish bulk dumps. There is no open-data export of Karnataka S&E registrations.
- **Synthesis approach.** Generate records against Form A's structure with realistic name / address / PAN distributions. Bootstrap names from the MCA Karnataka company list (Section 6.1) for legal-entity strings, perturb to model free-text drift.

---

## 2. KSPCB XGN — Karnataka State Pollution Control Board

**System.** XGN online consent application portal for **Consent for Establishment (CFE / CFExp), Consent for Operation (CFO), and Authorisations** under Hazardous Waste Management (HWM), Plastic Waste Management (PWM), E-Waste Management (EWM), and Bio-Medical Waste (BMW) Rules.

**Primary statutes.**
- Water (Prevention & Control of Pollution) Act, 1974
- Air (Prevention & Control of Pollution) Act, 1981
- Hazardous & Other Wastes (Management & Transboundary Movement) Rules, 2016
- Plastic Waste Management Rules, 2016 (and successors)

**Sources.**
- Portal: https://kspcb.karnataka.gov.in/xgn-online-consent-applications-cfecfexp-cfo-authorisation-hwm-pwm-ewm-bmw-rogw-login-here
- Application forms hub: https://kspcb.karnataka.gov.in/application-forms-0
- Checklist PDF: https://kspcb.karnataka.gov.in/sites/default/files/inline-files/checklis16102020_2_0.pdf
- XGN user-flow walkthrough (Scribd): https://www.scribd.com/document/758884253/XGN-Form

### 2.1 Industry classification (the categorical key that drives everything)

KSPCB classifies industries into colour-coded categories that govern the fee, validity period, and which form applies. **Every consent record carries this category** and the prototype must respect it because cadence and decay differ by category.

| Category | Pollution potential | Typical CFO validity | Notes |
|---|---|---|---|
| Red | High | 5 years | Most stringent; periodic compliance reports required. |
| Orange | Moderate | 10 years | Mid-cadence renewal. |
| Green | Low | 15 years | Long-cycle; consent is near-permanent. |
| White | Negligible | One-time, no consent required | Excluded from CFO. |

CFE validity is typically up to 15 years irrespective of category (per documented procedure).

### 2.2 Canonical fields on the consent application

Pieced together from the public XGN profile / form walkthroughs (the consent application is a multi-tab online form; we list tabs as logical record blocks). KSPCB does not publish a single Form-A-equivalent PDF; the production schema is what the portal collects across these tabs.

**Block A — Industry Profile**

| Field | Notes |
|---|---|
| Industry Name | Free text; the canonical business name. |
| Industry Category (R / O / G / W) | Categorical. |
| Sector / Process classification | Free text + dropdown to a KSPCB-maintained category list; mapped to NIC where the applicant supplies one. |
| Date of Commissioning | Date. |
| Date of Production Commencement | Date; distinct from commissioning. |
| Industrial Area | **Structured field**: e.g. "Peenya Industrial Area Phase 2". This is the cleanest locality field across the four systems and is what we should bootstrap our locality dictionary from. |
| Taluk | Structured. |
| District | Structured. |
| Pin code | Structured. |
| Latitude / Longitude | Captured for newer applications via XGN's map widget. |
| Plot / Survey number | Free text; quality varies. |

**Block B — Identifiers**

| Field | Notes |
|---|---|
| PAN | **Typically present** — KSPCB demands PAN at user-id creation. Highest PAN coverage among the four systems. |
| GSTIN | Often present, especially for Red / Orange. |
| CIN (where applicable) | Captured for incorporated entities. |
| Aadhaar | Required for the eSign step on the application form. |

**Block C — Pollution-source structure (per application)**

These are repeating sub-records, each producing its own event stream:

- **Air stack details** — repeating: stack ID, height, attached process, permissible PM/SO₂/NOₓ limits.
- **Water details** — Water Consumption (W.C.), Wastewater Generation (WWG), discharge point.
- **Hazardous waste category & quantity** — repeating per category code (under HWM 2016 schedules).

**Block D — Consent meta**

| Field | Notes |
|---|---|
| Consent file number | The persistent KSPCB identifier. Format: alphanumeric with regional-office prefix. |
| Consent type | CFE / CFExp / CFO / Renewal / Amendment / CCA. |
| Issued date | Date. |
| Valid until | Date — **drives the renewal cadence parameter τ in the activity engine**. |
| Issuing Regional Office | Categorical (Bangalore Urban, Bangalore Rural, Mysuru, etc.). |

### 2.3 Quirks that affect entity resolution

- **2024 CCA consolidation.** KSPCB consolidated several consent types into the Combined Consent and Authorization (CCA) document. Historical records use the older CFE/CFO format; newer records may use CCA. The activity engine's event-type vocabulary must accept both, and the effective-date window separates them.
- **Industrial Area as a structured field.** Of the four systems we surveyed, only KSPCB stores Industrial Area / Taluk / District separately. Every other system has them embedded in free-text address. We should ingest KSPCB first and use its structured locality vocabulary as the canonical seed for the locality-normalisation dictionary.
- **Auto-renewal under EoDB.** Per the September 2020 EoDB circular, certain Green / Orange categories receive auto-renewal on submission of compliance documents. A renewal event in this regime is weaker activity signal than one under manual scrutiny — same regime-aware decay logic as e-Karmika applies.
- **Regional office prefix in the consent number** is a routable-jurisdiction signal but not a stable cross-record key (offices have been re-jurisdictioned).

### 2.4 Data availability for prototyping

- **Schema confidence: HIGH for structure, MEDIUM for exact field labels.** No single canonical PDF; reconstructed from official portal walkthrough and the procedure documents. We should verify field labels against an actual XGN screenshot before freezing the synthetic schema.
- **Real-data availability: PARTIAL.** Some KSPCB compliance summaries appear on the public portal under "Green Rating Industries" but not as bulk dumps. Individual consent letters are downloadable per industry.
- **Verification action.** Confirm the Air stack / Water / Hazardous waste sub-record fields by getting one real CFO PDF from the public portal.

---

## 3. FBIS — Department of Factories, Boilers, Industrial Safety & Health (eSurakshate)

**System.** FBIS / e-Surakshate, the online portal for registration, plan approval, license issuance, and renewal under the **Factories Act, 1948** and **Karnataka Factories Rules, 1969**.

**Primary statute / forms.**
- Form 1 — Application for permission for construction / extension / use of building as a factory (Rule 3).
- Form 1A — Certificate of Stability (issued by qualified structural engineer).
- **Form 2** — Application for registration of a factory and grant / renewal of licence (Rule 4). **The principal record.**
- Form 3 — The Licence itself (issued by Chief Inspector).
- Form 20 — Annual Return (statutory; due 1 February for the preceding calendar year).
- Form 21 — Half-yearly Return (due 15 July).
- Form 4 — Certificate of Fitness (issued by Certifying Surgeon for adolescents/children).

**Applicability.** Section 2(m) of the Factories Act: 10+ workers with power, or 20+ without power. State Government may notify lower thresholds.

**Sources.**
- Portal: https://surakshate.karnataka.gov.in/FBIS/app/login (login wall) and https://esuraksha.karnataka.gov.in/english (department info)
- Form 2 online help: https://surakshate.karnataka.gov.in/FBIS/FORM2_ONLINEHELP2.jsp
- Karnataka Factories Rules 1969 PDF: https://www.comply360.in/labor-law-library/wp-content/uploads/2024/02/THE-KARNATAKA-FACTORIES-RULES-1969-.pdf
- Karnataka Factories Rules summary: https://www.greythr.com/wiki/acts/karnataka-factories-rules-1969/
- Procedure note (PulseHRM): https://www.pulsehrm.com/Content/themes/PulseHRM/Forms/karnataka/Karnataka-Factory-Rules-1969.pdf

### 3.1 Canonical fields on Form 2 (registration + license)

Form 2 captures the following — reconstructed from Rule 4 of Karnataka Factories Rules 1969 and the standard Form-2 schema as printed in the Rules:

**Block A — Factory & premises**

| Field | Notes |
|---|---|
| Name of the factory | Canonical name. |
| Postal address of the factory premises | Free text. |
| Village / Town | Free text. |
| Taluk / District | Free text (not always separated — schema drift on amendment). |
| Postal pin code | Free text within the address block. |
| Telephone, fax, email | Optional. |
| Survey number / Plot number | Free text. |
| Nature of manufacturing process | Free text + NIC code where supplied. |
| Maximum number of workers proposed | Integer. |
| H.P. / K.W. of installed power | Numeric — **a fee determinant**. |

**Block B — Occupier details**

The "Occupier" is the legally responsible person under Section 2(n) — typically a Director nominated by the Board for incorporated entities. Form 2 captures:

| Field | Notes |
|---|---|
| Name of Occupier | Personal name. |
| Designation | Director / Partner / Proprietor. |
| Residential address | Free text. |
| Telephone | Optional. |
| PAN of the Occupier | Captured at user signup on FBIS portal — required to create the FBIS user account. |

**Block C — Manager details**

The Manager is the day-to-day in-charge under Section 7. Fields parallel the Occupier block.

**Block D — Constitution of factory**

| Field | Notes |
|---|---|
| Type of constitution | Proprietorship / Partnership / Pvt Ltd / Public Ltd / LLP / Cooperative / Government. |
| List of Directors / Partners | Repeating with name, address, designation. |
| Date of incorporation / partnership-deed registration | Date. |

**Block E — License & fee**

| Field | Notes |
|---|---|
| Licence number (Form 3) | The persistent FBIS identifier. |
| Form 2 registration number | Internal; persists across license renewals. |
| Treasury challan number, date, amount | The fee event — ingested as activity. |
| Period for which license is sought | 1 / 2 / 3 years (max 3 since the EoDB amendments). |

### 3.2 Notice of Occupation and Change of Manager (Rule 12 → Form 2)

Per Rule 12 (as amended in 2017): **Notice of occupation shall be in Form No. 2 in duplicate by post or through e-Surakshate.** Notice of Change of Manager is **Form 3-A**. These are filed within 15 days of the change. They are the primary "mutation" events the linkage layer must track to keep the UBID's leadership graph current.

### 3.3 Periodic returns (the activity-stream events)

| Form | Cadence | Due date | Notes |
|---|---|---|---|
| Form 20 (Annual Return) | 365d | 1 February (for previous CY) | Strong activity signal. |
| Form 21 (Half-yearly Return) | 183d | 15 July | Mid-strength signal. |
| Form 22 (Notice of accident / dangerous occurrence) | event-driven | — | Not a continuity signal but presence-of-life. |

### 3.4 Quirks that affect entity resolution

- **Deemed registration after 3 months.** If no order is communicated within 3 months of Form 2 submission, registration is deemed granted (Rule 5). Synthetic generation should reflect this — some records will be live with no explicit "approved" timestamp.
- **License amendment without re-registration.** Changes to name, manager, worker count, or H.P. trigger an amended licence under Rule 6 — same Form 2 registration number persists. The licence number (Form 3) is the appropriate persistent identifier; the Form 2 registration number persists across name changes too but is internal.
- **Hazardous vs Non-hazardous track.** Hazardous (First Schedule of the Act) factories follow a stricter procedure with additional Health & Safety Policy attached. The category should be captured in the synthetic schema.
- **2017 Karnataka Factories (Amendment) Rules** moved Form 2 fully online via e-Surakshate. Records before that date may have been manually digitised, with predictably worse free-text quality.

### 3.5 Data availability for prototyping

- **Schema confidence: HIGH.** Form 2 is statutory and printed in the 1969 Rules.
- **Real-data availability: HIGH (indirect).** The **Annual Survey of Industries (ASI)** by MOSPI publishes microdata at the factory level for all states including Karnataka, freely downloadable. ASI's frame is built from the Chief Inspector of Factories' lists. ASI 2016-17 onwards is on https://microdata.gov.in/NADA/index.php/catalog/ASI . For 2022-23, the registered universe is roughly 2.55 lakh factories nationally; Karnataka contributes a major share.
- **Synthesis approach.** Use ASI block-level statistics (employment band, NIC distribution, district distribution) to seed a realistic Karnataka factory population, then generate Form 2 records around that distribution.

---

## 4. BESCOM — Bangalore Electricity Supply Company Limited

**System.** BESCOM, the LT/HT electricity distribution utility for 8 districts including Bangalore Urban / Rural. Not a regulatory system — a billing system — but the richest activity-signal source in the entire stack because of monthly bill cadence.

**Primary references.**
- BESCOM consumer portal (login + bill view): https://bescom.karnataka.gov.in/
- Consumer-number documentation: https://www.bajajfinserv.in/how-to-find-bescom-electricity-bill-consumer-number
- KarnatakaOne BESCOM helper: https://www.karnatakaone.gov.in/Info/Public/BESCOMHelp
- Identifier history (legacy → new RR format): http://govt-links.blogspot.com/2012/01/online-bescom-bill-payment-no-longer.html

### 4.1 The three identifiers BESCOM uses (and how they break)

| Identifier | What it is | Stability | Format |
|---|---|---|---|
| **RR Number** (Revenue Register Number) | The connection number painted on the meter board. **Tied to the physical premise / meter, not the consumer.** | Stable for the meter's life. | Two regimes: legacy 10-char alphanumeric (e.g. `MS3EH12345`) and post-2012 10-digit numeric (e.g. `0123456789`). Both still appear in current bills, with the legacy in brackets. |
| **Account ID** | A 10-digit number introduced post-2012 along with the new RR format. Used for online portal lookup. | Stable per account. | 10 digits. |
| **K Number / Consumer Number** | A consumer-tied identifier used for some billing flows. | Tied to consumer; can change on transfer. | Variable. |
| **Sub-Division / Location code** | Geographic routing code (e.g. W3, W4, S3, C1). | Stable per area; reorganised periodically. | Alphanumeric prefix. |

A consumer with an old bill and a new bill will see all of these — and the RR–to–Account mapping is internal to BESCOM. There is no public API; the closest public surface is the bill PDF.

### 4.2 Canonical fields on a BESCOM bill (the ingest surface)

| Field | Notes |
|---|---|
| RR Number | Stable physical-meter key. |
| Account ID | 10-digit billing account. |
| K Number / Consumer Number | Consumer-tied. |
| Sub-Division code | Routing. |
| Consumer Name | **Often the property owner, not the business operating there.** Quoted directly in the proposal as the BESCOM messy-data risk. |
| Service address | Free text; quality is bottom-tier among the four systems. |
| Tariff category | LT-1 (domestic), LT-2 (commercial), LT-3 (industrial), LT-4 (water-supply / streetlight), LT-5 (agriculture), HT-1 / HT-2 (high-tension industrial). **A categorical filter we'd use to scope to "business" connections only.** |
| Sanctioned load / contract demand | Numeric (kW or kVA). |
| Bill month | Date. |
| Units consumed | Numeric (kWh). |
| Bill amount | Numeric. |
| Payment status | Paid / Unpaid / Disputed. |

### 4.3 Event types BESCOM produces

| Event | Cadence | Strength as continuity signal |
|---|---|---|
| Bill generated | 30d | Medium (weight 0.5 in the proposal). |
| Bill paid (non-zero) | 30d | **Strongest** continuity signal in the whole system (weight 0.9). |
| Zero-consumption month | 30d | Negative evidence (weight 0.4 negative). |
| Disconnect | event | Strong terminal-ish (weight 0.9), reversible. |
| Reconnect | event | Strong revival signal. |
| Tariff category change | event | A real-world signal of change-of-business-use; routes to reviewer for re-linkage scrutiny. |

### 4.4 Quirks that affect entity resolution

- **Owner-of-record vs operator.** A factory operating from premises rents, so its BESCOM connection is in the landlord's name. The "Consumer Name" field is wrong from the linkage POV. Address-only matching with an inflated threshold is the safest approach (called out in the proposal).
- **Three identifiers, none of which are PAN / GSTIN.** This is exactly why BESCOM clusters among itself first (RR ↔ Account ↔ K Number) before being attached to a UBID.
- **Identifier-format breakage 2012.** Both RR formats coexist in current bills. Synthetic generation should produce both formats with the legacy form in brackets.
- **No bulk download.** The portal is consumer-facing; there is no public bulk export. Real BESCOM data is the bottleneck for any pilot.

### 4.5 Data availability for prototyping

- **Schema confidence: HIGH for bill structure.** The bill is what the consumer sees and what we'd ingest from any data-sharing pipe.
- **Real-data availability: NONE without a data-sharing agreement.** Plan to synthesise BESCOM connections that align to factory addresses generated for FBIS and KSPCB.
- **Synthesis approach.** For each FBIS / KSPCB factory, generate 1–3 BESCOM connections (one main, optional water/streetlight). Make 30% of connection-holder names *not* match the factory name (landlord case). Make 5% have stale addresses (recent-move). This is exactly the dirty-data realism that exercises the linkage thresholds.

---

## 5. Central Government anchors — PAN, GSTIN, Udyam, MCA

These are **not Karnataka systems** but are referenced in records of all four state systems above and are the strongest cross-system identifiers we have.

### 5.1 PAN — Income Tax Department

**Format.** 10 characters: `[A-Z]{5}[0-9]{4}[A-Z]{1}` — 5 letters + 4 digits + 1 letter. The **4th character encodes entity type**:

| 4th char | Entity type | Implication for UBID |
|---|---|---|
| P | Individual / Proprietorship | **Soft-match in linkage** — single PAN can map to multiple distinct UBIDs (different establishments owned by same proprietor). Same Legal Entity parent. |
| C | Company | Unique legal entity. |
| F | Partnership Firm | Unique legal entity. |
| H | HUF (Hindu Undivided Family) | Unique legal entity. |
| T | Trust | Unique legal entity. |
| A | Association of Persons (AOP) | Unique legal entity. |
| B | Body of Individuals (BOI) | Unique legal entity. |
| L | Local Authority | Unique legal entity. |
| J | Artificial Juridical Person | Unique legal entity. |
| G | Government | Unique legal entity. |

The 5th character is the first letter of the surname (for individuals) or entity name (for non-individuals). This gives a weak structural cross-check on the name field.

**Validation.** No checksum that's publicly documented and reliable; structural validation via regex is the standard approach.

### 5.2 GSTIN — GST Network

**Format.** 15 characters: `[state:2][PAN:10][entity:1][Z][checksum:1]`.

- **Positions 1–2.** State code (Karnataka = `29`). National numbering.
- **Positions 3–12.** The **embedded PAN** of the legal entity. Same across all states for a multi-state entity. Extract via `gstin[2:12]`.
- **Position 13.** Entity / vertical number (1–9, A–Z). Lets a single legal entity hold multiple GSTINs in the same state for different verticals.
- **Position 14.** Always `Z`.
- **Position 15.** Checksum (alphanumeric).

**Implications for UBID.**
- The embedded PAN gives us a **free legal-entity anchor** even when only GSTIN is captured.
- Position 13 means GSTIN-to-UBID is **many-to-one**, never one-to-one — a single business establishment may run multiple verticals each with its own GSTIN.
- Cross-state operations: a Mumbai HQ + Bangalore branch share the embedded PAN but have different state-prefix GSTINs. Karnataka UBID is anchored on the `29...` GSTIN; the Mumbai GSTIN attaches to the same Legal Entity parent but **does not** receive a Karnataka UBID.

### 5.3 Udyam Registration — Ministry of MSME

**System.** https://udyamregistration.gov.in/ . Replaced Udyog Aadhaar in July 2020.

**Identifier format.** `UDYAM-XX-NN-NNNNNNN` where `XX` is the state code (KR = Karnataka), `NN` is the district code, and the trailing 7 digits are sequential. 19 characters total.

**Captured fields.**
- Aadhaar of applicant (mandatory)
- PAN (mandatory; auto-fetched from IT department)
- GSTIN (auto-fetched if registered)
- Name of enterprise
- Type of organisation (Proprietorship / HUF / Partnership / Co-op / Pvt Ltd / Public Ltd / LLP / Self-help group / Society / Trust)
- Plant location address (multiple plants supported)
- Office address
- Number of employees (Male / Female / Other)
- Investment in plant & machinery (auto-fetched from ITR)
- Turnover (auto-fetched from GST returns)
- NIC code(s) — **multiple supported** for multi-activity enterprises
- Bank account details
- Date of commencement

**Why it matters for UBID.**
- Udyam is **PAN- and GSTIN-linked at registration**, making it the cleanest cross-anchor record we can ingest.
- It exposes NIC codes natively — this is our cleanest sector-classification source.
- Multi-plant support means a single Udyam ID may map to multiple establishments → multiple UBIDs under one Legal Entity.

**Data availability.**
- District-wise aggregate counts: https://karnataka.data.gov.in/catalog/udyam-registration-msme-registration (Karnataka Department of Industries and Commerce, updated 2024).
- Bulk individual records: not public, but the dashboard at https://dashboard.msme.gov.in/Udyam_Statewise.aspx exposes filterable counts.

### 5.4 MCA Company Master Data

**System.** Ministry of Corporate Affairs MCA21 V3.

**Identifier format.** CIN (Corporate Identity Number) — 21 characters: `L/U + 5-digit industry code + 2-letter state + 4-digit year + 3-letter classification + 6-digit serial`. E.g. `U72200KA2010PTC053497` reads as "Unlisted, IT services, Karnataka, 2010, Private LTd Company, sequence 053497".

**Master-data fields exposed (free public lookup at mca.gov.in → "View Company / LLP Master Data"):**
- CIN, Company Name, ROC Code, Registration Number
- Company Category, Sub-category, Class
- Authorised Capital, Paid-up Capital
- Number of members
- Date of Incorporation
- Registered Office Address (free text)
- Email
- Listed / Unlisted
- ACTIVE compliance status
- Date of last AGM, Date of Balance Sheet
- Company Status (for e-filing) — Active / Strike-off / Dormant / Under Liquidation / Amalgamated etc.
- Charges (if any) — assets under charge, charge amount, dates
- Directors with DIN

**Data availability — this is our best real, bulk, downloadable Karnataka source.**
- Bulk Karnataka company master data Excel: http://reports.mca.gov.in/MinistryV2/archiveofmasterdatadetails.html — the file labelled *"Master Details of Companies registered: Karnataka (excel format) (9 MB)"* gives every Karnataka-registered company with the master fields above.
- We can use this as a **real seed** for Legal Entity and UBID generation: pull names, registered addresses, incorporation dates, status, then synthesise the per-department records (S&E, Factories, KSPCB, BESCOM) **around** these real entities. This gives synthetic data with realistic Bengaluru-address distribution, real Indian company-name patterns, and real PAN-prefix distributions (CIN 9–18 chars encode ROC etc., not PAN, but the entity types align).

---

## 6. Other open-data sources to seed synthesis

### 6.1 Open Government Data Portal (Karnataka)

- Portal: https://karnataka.data.gov.in/ and OpenCity mirror at https://data.opencity.in/dataset?organization=government-of-karnataka (115 Karnataka datasets)
- Most relevant for our use case: Economic Survey of Karnataka 2025-26 (sector breakdown), district-wise Udyam registration counts.

### 6.2 Annual Survey of Industries (ASI)

- Microdata portal: https://microdata.gov.in/NADA/index.php/catalog/ASI
- Available: ASI 2016-17 through ASI 2022-23 (latest released Sep 2024 for 2022-23).
- **What it gives us.** Unit-level data with NIC, employment, capital, output, state, district. Frame source = Chief Inspector of Factories (FBIS-equivalent). For 2022-23, the universe of registered factories with status open / existing-with-fixed-assets is 2,55,244 nationally; we can extract Karnataka subset.

### 6.3 NDAP (National Data and Analytics Platform)

- https://ndap.niti.gov.in/ — aggregated cross-source datasets from MOSPI / NITI Aayog. Useful for industrial-sector benchmarks at state / district level.

### 6.4 Pin code / Locality reference

- India Post pin-code directory: https://www.indiapost.gov.in/vas/pages/findpincode.aspx
- For Bengaluru locality canonicalisation: KSPCB structured Industrial-Area / Taluk / District field (ingested first per Section 2 above) is the recommended seed dictionary.

---

## 7. Cross-system field comparison (the consolidated view)

| Field | e-Karmika (S&E) | FBIS (Factories) | KSPCB (XGN) | BESCOM | Udyam | MCA |
|---|---|---|---|---|---|---|
| Primary unique ID | Establishment Reg No. (Form C) | Licence No. (Form 3) + Form 2 Reg No. | Consent file No. | RR No. + Account ID | UDYAM-KR-NN-NNNNNNN | CIN |
| PAN coverage | Partial (post-2019 better) | At Occupier signup | Typically present | Absent | **Mandatory, auto-verified** | Indirect (DIN→PAN of directors) |
| GSTIN coverage | Rare | Inconsistent | Often present | Absent | **Auto-fetched** | Not in master data |
| Address structure | Free text + Kannada | Free text | **Structured** (Industrial Area / Taluk / District) | Free text | Free text + multi-plant array | Free text (Registered Office) |
| Sector code | Free text "Nature of Business" | Free text + NIC where supplied | KSPCB category + NIC | Tariff category | **NIC code(s), native** | 5-digit MCA industry code in CIN |
| Activity events | Renewal + closure | Form 20 (annual), Form 21 (half-yr), licence renewal | CFE/CFO renewal, compliance reports | **Monthly bill / payment** | Annual self-declaration update | AGM date, balance-sheet date, charge events |
| Cadence (avg) | 5y (pre-2019) / 365d (post) | 365d / 183d | varies (5/10/15y by category) | **30d** | 365d (loose) | ~365d |
| Best for resolution | Name + PAN | PAN + occupier | PAN + structured address | Address-only (after BESCOM-internal cluster) | PAN + GSTIN combined | CIN + name |
| Best for activity | Renewal cadence | Returns | Compliance + renewal | **Bill stream** | Update events (weak) | AGM / charge events |

---

## 8. Recommended schema for synthetic data generation

Based on the above, a single canonical record to drive synthetic-data generation per source system. Generate per-system records from a shared underlying "ground-truth" entity, then introduce realistic drift (typos, missing fields, bilingual variants, format breaks).

**Ground-truth entity (internal — not visible to the platform):**

```
GroundTruthEntity {
  legal_entity_id: UUID                  # Internal, hidden from prototype
  pan: str | None                        # 70% present, follows ABCDE1234F format
  pan_4th_char: enum                     # P / C / F / H / T / ...
  gstin_29: str | None                   # 60% present, '29' + pan + entity_digit + 'Z' + checksum
  legal_form: enum                       # Proprietorship / Partnership / PvtLtd / ...
  name_canonical_english: str
  name_canonical_kannada: str | None     # 40% have Kannada original
  establishments: list[Establishment]    # 1..5
}

Establishment {
  ubid: UUID                             # Internal, hidden
  premise_canonical: PremiseAddress      # Pin / Industrial Area / Taluk / District / Door
  sector: NIC_5digit
  size_class: enum                       # micro / small / medium / large
  date_commenced: date
  state: enum                            # Active / Dormant / Closed (ground truth for evaluation)
  bescom_connections: list[BESCOMConn]   # 1..3
  source_records: list[SourceRecord]     # 1..5 across the 4 systems
}
```

**Per-system materialisations** then perturb the ground truth — strip PAN with 30% probability for S&E, transliterate 40% of names to Kannada for S&E, replace consumer-name with a random "owner name" for 30% of BESCOM, drop pin code into free-text address for FBIS, etc. The goal is a synthetic corpus where the four-stage pipeline (canonicalise → block → score → cluster) gets realistic exercise.

---

## 9. Verification next steps before freezing the schema

These are the sanity-checks we should do before committing to synthetic-data generation:

1. **Get one real CFO PDF from KSPCB's public portal** to verify Block A/B/C/D field labels exactly. The `Green Rating Industries` page on the KSPCB portal links to public consent docs.
2. **Download the MCA Karnataka master-data Excel** (9 MB) and inspect the actual column headers and value distributions. This is our richest real-data seed.
3. **Pull ASI 2022-23 unit-level data** for Karnataka and check the field-block layout against our Form 2 reconstruction. Discrepancies indicate either ASI uses a different schema (likely — ASI Part I / Part II is a separate questionnaire) or that we're missing fields.
4. **Compare a sample BESCOM bill** (anyone on the team with one, redacted) against Section 4.2 to confirm the field set.
5. **Pull 5 e-Karmika certificates** issued post-2019 from any third-party site that has examples to confirm the certificate's printed structure aligns with Form C.

Once these five are done, we have a confidence-tested schema and can generate synthetic data with provenance for every field decision.

---

## 10. References (consolidated)

- e-Karmika portal: https://www.ekarmika.karnataka.gov.in/
- Form A (Karnataka S&E) PDF: https://www.datocms-assets.com/40521/1625469907-kar-se-form-a-combined-application-for-establishment-registration-renewal-change.pdf
- KSPCB application forms: https://kspcb.karnataka.gov.in/application-forms-0
- KSPCB XGN portal: https://kspcb.karnataka.gov.in/xgn-online-consent-applications-cfecfexp-cfo-authorisation-hwm-pwm-ewm-bmw-rogw-login-here
- KSPCB application checklist PDF: https://kspcb.karnataka.gov.in/sites/default/files/inline-files/checklis16102020_2_0.pdf
- FBIS portal: https://surakshate.karnataka.gov.in/FBIS/app/login
- Department of Factories: https://esuraksha.karnataka.gov.in/english
- Karnataka Factories Rules 1969 (full text): https://www.comply360.in/labor-law-library/wp-content/uploads/2024/02/THE-KARNATAKA-FACTORIES-RULES-1969-.pdf
- Karnataka Factories (Amendment) Rules 2017 notification: https://kea.co.in/wp-content/uploads/2023/04/circular-113-2017-AMENDMENT-TO-KARNATAKA-FACTORIES-RULES-1969.pdf
- BESCOM consumer portal: https://bescom.karnataka.gov.in/
- MCA Karnataka master data (bulk Excel): http://reports.mca.gov.in/MinistryV2/archiveofmasterdatadetails.html
- Udyam dashboard: https://dashboard.msme.gov.in/Udyam_Statewise.aspx
- Udyam Karnataka district-wise dataset: https://karnataka.data.gov.in/catalog/udyam-registration-msme-registration
- ASI microdata portal: https://microdata.gov.in/NADA/index.php/catalog/ASI
- Karnataka Open Data Portal: https://karnataka.data.gov.in/
- OpenCity Karnataka mirror: https://data.opencity.in/dataset?organization=government-of-karnataka
- NDAP (NITI Aayog): https://ndap.niti.gov.in/
