---
type: interview-transcript
company: Marschkamp Fleisch GmbH & Co. KG
synthetic: true
governance: D5-wholly-synthetic
department: change-and-release-management
unit: it
interviewee: Kai Brüning
owner: Kai Brüning
facilitator: Franziska Dohm
date: 2025-02-25
covered: health, financial, legal, image, operational
source: prior BIA record 3.1
---

# Change and release management BIA interview

**Date:** 25 February 2025, 11:58  
**Participants:** Kai Brüning (Head of IT Service Management, process owner); Levke Martens (Release Manager); Franziska Dohm (BCM Officer, interviewer)  
**Record:** prior BIA record 3.1, Change and release management. Synthetic demo data.

---

Franziska Dohm: Thank you for the time, Kai. First the process itself: what does it do, and where does it sit?

Kai Brüning: Planning, steering and implementing changes to IT systems, applications and infrastructure, to minimise risks, ensure stability and deliver new or improved functions under control. It is a support process, and its process owner is the head of IT service management. The organisational unit is IT.

Franziska Dohm: Then the impact of an outage, category by category, at 1 h, 2 h, 4 h, 8 h, 24 h, 72 h and 168 h. Give each one in words, then on the scale: 1 none, 2 low, 3 medium, 4 high, 5 very high.

Kai Brüning: Health of persons. In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h none.

Kai Brüning: Impact health: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 1.

Kai Brüning: Financial. In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h none.

Kai Brüning: Impact financial: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 1.

Kai Brüning: Legal. Changes can have time-critical requirements (legislative, security). In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h low.

Kai Brüning: Impact legal: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 2.

Kai Brüning: Image. In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h none.

Kai Brüning: Impact image: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 1.

Kai Brüning: Operational. Changes can have time-critical requirements (legislative, security). In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h low.

Kai Brüning: Impact operational: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 2.

Franziska Dohm: How high is the potential threat, and what do you set for recovery?

Kai Brüning: The potential threat is low. The recovery time was set at >168 h. What counts are the impacts shown in the criticality assessment, and the possibility of continuing the process in the emergency operation described until it is restored.

Kai Brüning: RTO: >168 h.

Kai Brüning: MTPD: >168 h.

Kai Brüning: The process is not relevant to the BCMS.

Franziska Dohm: What could make the process fail?

Kai Brüning: Failure of the IT service management system; staff shortage in release management or in the approval boards; missing or contradictory change documents; failure of central means of communication; test or deployment environments not available.

Franziska Dohm: And how do you run it in emergency operation?

Kai Brüning: Only security-critical, legally required and operations-stabilising changes are handled. Request, risk analysis, approval, implementation and fallback plan are documented in a standardised emergency form. Approvals are given by phone or through Microsoft Teams and logged by release management. Releases without priority are suspended.

Franziska Dohm: Last, the resources the process needs.

Kai Brüning: IT systems. Atlassian Jira: RPO <24 h, RTO >168 h. Protection need: confidentiality medium (change requests hold internal technical and organisational information); integrity high (wrong approvals or status data can lead to uncontrolled changes); authenticity high (approvals must be clearly assigned to an authorised person). Atlassian Jira is used to record, assess, approve, schedule and follow up changes and releases. Workaround: Change requests are documented in an approved emergency form. Coordination and approval go by phone or through Microsoft Teams.

Kai Brüning: IT systems. Microsoft 365: RPO <24 h, RTO >168 h. Protection need: confidentiality medium (e-mails and documents hold internal planning and approval information); integrity medium (errors are recognisable and can be corrected from the change documentation); authenticity medium (senders and those handling must be traceable). Microsoft 365 supports communication, scheduling, documentation and providing release documents. Workaround: Communication goes by phone. Approvals and minutes are documented locally in an encrypted template and entered later.

Kai Brüning: Roles. Release manager: 2 in normal operation, 1 in emergency operation, needed within >168 h, remote or office. Plans releases, coordinates dependencies and ensures controlled implementation. Workaround: An available release manager takes over prioritisation and coordination.

Kai Brüning: Roles. Release controller: 2 in normal operation, 1 in emergency operation, needed within >168 h, remote or office. Checks completeness, approval status and compliance with the release rules. Workaround: An available release controller continues documentation and quality checks.

Kai Brüning: Depends on: Atlassian Jira, Microsoft 365, Release manager, Release controller.

Franziska Dohm: Thank you.
