# RegLens — Bank of Namibia Fintech Youth Programme Submission Note

**Programme:** Bank of Namibia Innovation Hub — Fintech Youth Programme (FYP)
**Solution:** RegLens — Adaptive Agentic Regulatory Intelligence (RegTech)
**Prepared:** July 2026

This note maps RegLens to the six sections of the FYP application form
so the online form can be completed directly from it. Fields marked
`[TO FILL]` require personal or entity details that must be entered by
the applicant.

---

## Section 1 — Applicant Details

- Founder name, date of birth, gender, nationality, ID number: `[TO FILL]`
- Contact details, residential and postal address: `[TO FILL]`
- Registered entity (if applicable): legal name, registration number,
  year of establishment, management, employee count: `[TO FILL]`
  (If not yet registered, apply as individual founder(s) — the FYP
  supports pre-registration ideation through to maturity stages.)

---

## Section 2 — Fintech Solution Overview

**Solution name:** RegLens

**Primary service category:** RegTech
(the FYP form lists RegTech alongside payments, lending, insurance,
savings, AgriTech, GovTech, CleanTech — RegLens is squarely RegTech)

**Target markets (form checkboxes):**
- Government (regulators: Bank of Namibia, NAMFISA)
- Cross-border users (SADC payment and compliance coordination)
- SMEs (indirectly: reduced compliance burden lowers the cost of
  serving small businesses)

**Solution description (150–200 words, ready to paste):**

> RegLens is an adaptive artificial-intelligence system that helps
> regulators find and fix "policy sludge" — overlapping, inconsistent,
> and outdated regulatory obligations. A regulator loads its regulatory
> documents (determinations, circulars, acts, international standards)
> and RegLens automatically discovers the regulatory context from the
> documents themselves. It then provides three capabilities. First,
> sludge detection: it finds duplicated and conflicting obligations
> across the corpus, with every finding citing the exact provisions and
> requiring human expert approval before publication. Second,
> pre-rulemaking checks: before a new determination is published,
> RegLens compares the draft against all existing instruments and flags
> overlaps and contradictions in minutes. Third, cross-border
> comparison: it compares two frameworks — for example the Namibian
> AML framework against the FATF Recommendations — and returns a gap
> analysis with a harmonisation score and concrete coordination
> recommendations. RegLens runs as a single container with local
> document parsing, so no regulatory corpus data needs to leave the
> regulator's environment.

**Estimated market size:** 16 SADC central banks and financial sector
authorities; ESAAMLG member states; regional bodies (SADC CCBG, COMESA);
plus commercial compliance teams at banks and PSPs operating across
SADC corridors. `[REFINE with figures before submission]`

**Development stage (form options: ideation → maturity):**
Functional minimum viable product — working ingestion pipeline, analysis
API, human-in-the-loop review workflow, and CLI; prepared as a CDIR
Global 'Agentic Regulator' Hackathon 2026 submission.

**Prototype proof (image upload):** screenshot of the CLI analysis run
and corpus map. `[ATTACH]`

**Risk assessment and mitigation:**
- AI error / false findings → mandatory human-in-the-loop approval;
  citation validator rejects unverifiable citations; all output is
  explicitly advisory.
- Data sensitivity → public/synthetic corpora only; local (Docling)
  parsing keeps documents inside the regulator's environment; the
  database (Neon Postgres) is server-side only, never browser-exposed.
- Key-person dependency → standard stack (Python, Postgres) with
  documented architecture; no bespoke infrastructure.
- Model/vendor dependency → provider-agnostic LLM interface (any
  OpenAI-compatible endpoint, including locally hosted models).

**Competitive landscape:** Regulatory gap analysis in SADC today is
manual — consulting engagements and bilateral workshops measured in
months. International RegTech tools focus on compliance for firms, not
sludge detection for regulators, and none are adaptive to an arbitrary
corpus without configuration. RegLens's corpus-agnostic design is the
differentiator.

**Revenue model:** deployment and support subscriptions for regulators
and regional bodies; per-engagement analysis for framework comparison
projects (e.g. mutual evaluation preparation); the core system remains
open source (MIT) to build trust with public institutions.

**User statistics:** pre-launch; hackathon pilot corpus and demo
sessions. `[UPDATE at submission]`

---

## Section 3 — Financial Inclusion

RegLens serves inclusion indirectly but measurably:

- **Remittance corridors:** AML/CFT de-risking already constrains
  correspondent banking access in SADC. Duplicated and divergent
  obligations raise compliance costs that are passed to consumers as
  fees or service withdrawal. Harmonisation directly lowers the cost
  of serving cross-border remittance users — a primary income channel
  for many Namibian and SADC households.
- **Regulatory capacity:** every supervisory hour freed from manual
  framework comparison is an hour available for inclusion-focused
  supervision (mobile money, agent networks, micro-lending oversight).
- **Cheaper compliance for small players:** cleaner, consolidated
  rulebooks lower the fixed cost of entry for young Namibian fintech
  startups — the FYP's own constituency.

Rural accessibility features (low bandwidth, USSD, local language) are
not applicable to a regulator-facing tool; the inclusion impact operates
through the regulatory system itself.

---

## Section 4 — Team Structure

- Wiebe Geldenhuys — System Architecture, Database Design
- Jerobeam Nambili — Product Requirements, SADC Field Context
- George Nekwaya — Development, Analytics

Governance: `[TO FILL — select the form option matching current
structure; formalise advisory oversight if entity registration
proceeds]`

---

## Section 5 — Programme Support and Funding

**Support sought (form checkboxes):**
- Regulatory guidance — direct engagement with BoN on how a sludge
  intelligence tool fits supervisory workflows
- Regulatory sandbox testing — pilot RegLens against a public BoN
  determination corpus under Innovation Hub supervision
- Ecosystem access — introductions to NAMFISA, SADC CCBG contacts,
  and commercial compliance teams
- Mentorship and pitch coaching — sharpening the regulator-facing
  value proposition
- Investment readiness — structuring for public-sector procurement

**Hackathon participation:** Yes — the team is submitting RegLens to
the CDIR Global 'Agentic Regulator' Hackathon 2026 and welcomes the
FYP hackathon pathway.

**Prior funding:** self-funded development to date. `[CONFIRM]`

**Intended use of programme funds (if accessed):** pilot deployment
with one Namibian regulator (hosting, document corpus preparation,
evaluation study), plus LLM inference costs for the pilot period.

---

## Section 6 — Declarations and Documents

Mandatory acknowledgements (tick on form): originality, truthfulness,
understanding that acceptance is not regulatory approval, AML/CFT
screening consent, compliance agreement.

Supporting documents checklist:
- [ ] Founding statement / company profile (if registered)
- [ ] Tax and employment standing confirmations
- [ ] Founder CVs
- [ ] Business plan (the CDIR concept note `docs/concept_note.md` and
      technical description `docs/thesis.md` form the core; add a
      short financial annex)
- [ ] Prototype image

---

## Positioning Notes for the Form

- Lead with the **Namibia pre-rulemaking example**: BoN drafts a new
  Payment System Determination; RegLens checks it against existing
  determinations, the NPS Act, SADC guidelines, and FATF guidance
  before publication. This is the single most concrete BoN-relevant
  use case.
- The FYP emphasises "close proximity to the regulatory and policy
  environment" — RegLens is unusual in that the regulator is the user,
  making the Innovation Hub the ideal (arguably only) launch channel
  in Namibia.
- Keep the adaptive/agnostic framing: nothing in RegLens is hardcoded
  to Namibia; it is built from the Namibian/SADC context but deploys
  against any corpus. This addresses both local relevance and scale
  questions in one line.

## Sources

- Bank of Namibia Innovation Hub — Fintech Youth Programme form:
  https://www.bon.com.na/About-Us/Innovation-Hub/Fintech-Youth-Programme-Form.aspx
- Bank of Namibia Innovation Hub: https://www.bon.com.na/About-Us/Innovation-Hub.aspx
- MTC Namibia partnership with Bank of Namibia on the Fintech Youth
  Programme (TechAfrica News, October 2025):
  https://techafricanews.com/2025/10/21/mtc-namibia-partners-with-bank-of-namibia-to-launch-fintech-youth-programme/
