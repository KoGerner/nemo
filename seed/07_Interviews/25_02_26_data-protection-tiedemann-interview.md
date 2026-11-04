---
type: interview-transcript
company: Marschkamp Fleisch GmbH & Co. KG
synthetic: true
governance: D5-wholly-synthetic
department: data-protection
unit: it
interviewee: Ulrike Tiedemann
owner: Ulrike Tiedemann
facilitator: Franziska Dohm
date: 2025-02-26
covered: health, financial, legal, image, operational
source: prior BIA record 3.9
---

# Data protection management BIA interview

**Date:** 26 February 2025, 10:00  
**Participants:** Ulrike Tiedemann (Data Protection Officer, process owner); Finn Mommsen (Data Protection Coordinator); Franziska Dohm (BCM Officer, interviewer)  
**Record:** prior BIA record 3.9, Data protection management. Synthetic demo data.

---

Franziska Dohm: Thank you for the time, Ulrike. First the process itself: what does it do, and where does it sit?

Ulrike Tiedemann: Reporting data protection incidents under the GDPR. The systematic identification, classification, processing and protection of personal data under legal requirements (for example the GDPR), including implementing technical and organisational measures to ensure the confidentiality, integrity and availability of these data. It is a support process, and its process owner is the data protection officer. The organisational unit is IT.

Franziska Dohm: Then the impact of an outage, category by category, at 1 h, 2 h, 4 h, 8 h, 24 h, 72 h and 168 h. Give each one in words, then on the scale: 1 none, 2 low, 3 medium, 4 high, 5 very high.

Ulrike Tiedemann: Health of persons. In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h none.

Ulrike Tiedemann: Impact health: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 1.

Ulrike Tiedemann: Financial. In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h none.

Ulrike Tiedemann: Impact financial: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 1.

Ulrike Tiedemann: Legal. Breach of the legal reporting deadlines for reporting an incident. In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h high.

Ulrike Tiedemann: Impact legal: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 4.

Ulrike Tiedemann: Image. In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h none.

Ulrike Tiedemann: Impact image: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 1.

Ulrike Tiedemann: Operational. In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h none.

Ulrike Tiedemann: Impact operational: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 1.

Franziska Dohm: How high is the potential threat, and what do you set for recovery?

Ulrike Tiedemann: The potential threat is high. The recovery time was set at 72 h. What counts are the impacts shown in the criticality assessment, and the possibility of continuing the process in the emergency operation described until it is restored.

Ulrike Tiedemann: RTO: 72 h.

Ulrike Tiedemann: MTPD: >168 h.

Ulrike Tiedemann: The process is relevant to the BCMS.

Franziska Dohm: What could make the process fail?

Ulrike Tiedemann: Failure of the reporting and documentation systems; staff shortage in the data protection function or in the departments; late or incomplete reporting of a data protection incident; loss of, or unauthorised access to, case files; failure of secure communication channels.

Franziska Dohm: And how do you run it in emergency operation?

Ulrike Tiedemann: Data protection incidents are reported by phone or through an approved internal substitute channel. An encrypted emergency form documents the facts, the data affected, the time, the risks, the measures, those responsible and the deadlines. The data protection officer prioritises cases that may have to be reported. Personal data are not transferred through private e-mail accounts.

Franziska Dohm: Last, the resources the process needs.

Ulrike Tiedemann: IT systems. Atlassian Jira Service Management: RPO <1 h, RTO 72 h. Protection need: confidentiality very high (cases hold personal data and details of data protection breaches); integrity very high (facts, deadlines and measures must be documented completely and correctly); authenticity very high (those reporting, handling and approving must be clearly attributable). Atlassian Jira Service Management records, assesses and assigns data protection incidents and tracks their deadlines. Workaround: Data protection incidents are taken by phone on a local emergency form, or through an approved alternative internal reporting channel.

Ulrike Tiedemann: IT systems. Microsoft 365: RPO <1 h, RTO 72 h. Protection need: confidentiality very high (e-mails and documents can hold special categories of personal data); integrity very high (reports and assessments must be unaltered and complete); authenticity very high (senders, those handling and approvals must be traceable). Microsoft 365 supports secure communication, documentation and collaboration on data protection incidents. Workaround: Reporting by phone and a local encrypted emergency form are used. Personal data are not sent through private e-mail accounts.

Ulrike Tiedemann: IT systems. Microsoft SharePoint Online: RPO <1 h, RTO 72 h. Protection need: confidentiality very high (the filing holds personal data, assessments and correspondence with authorities); integrity very high (documents and deadlines must be complete and correct); authenticity very high (access and changes must be traceable). Microsoft SharePoint Online is the protected filing for case files, evidence, templates and reports to authorities. Workaround: Approved encrypted offline templates are used locally and moved into the protected filing after restoration.

Ulrike Tiedemann: Roles. Data protection officer: 3 in normal operation, 1 in emergency operation, needed within 72 h, remote or office. Assesses data protection incidents, coordinates measures and decides on the reports needed. Workaround: Availability from an internal and external pool of deputies.

Ulrike Tiedemann: Roles. Data protection coordinator: 4 in normal operation, 1 in emergency operation, needed within 72 h, remote or office. Supports case intake, documentation, communication and follow-up. Workaround: A coordinator takes over recording, clarifying the facts and deadline control.

Ulrike Tiedemann: Depends on: Atlassian Jira Service Management, Microsoft 365, Microsoft SharePoint Online, Data protection officer, Data protection coordinator.

Franziska Dohm: Thank you.
