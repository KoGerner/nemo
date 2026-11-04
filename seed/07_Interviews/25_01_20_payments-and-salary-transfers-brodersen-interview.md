---
type: interview-transcript
company: Marschkamp Fleisch GmbH & Co. KG
synthetic: true
governance: D5-wholly-synthetic
department: payments-and-salary-transfers
unit: hr
interviewee: Heike Brodersen
owner: Heike Brodersen
facilitator: Franziska Dohm
date: 2025-01-20
covered: health, financial, legal, image, operational
source: prior BIA record 2.2
---

# One-off payments and salary transfers BIA interview

**Date:** 20 January 2025, 11:51  
**Participants:** Heike Brodersen (Head of Payroll, process owner); Jörn Lüders (Senior Payroll Specialist); Franziska Dohm (BCM Officer, interviewer)  
**Record:** prior BIA record 2.2, One-off payments and salary transfers. Synthetic demo data.

---

Franziska Dohm: Thank you for the time, Heike. First the process itself: what does it do, and where does it sit?

Heike Brodersen: The process covers recording, checking, releasing and transmitting one-off payments and salary transfers. Payment data are reconciled with the released payroll and master data. It is a support process, and its process owner is the head of payroll. The organisational unit is human resources.

Franziska Dohm: Then the impact of an outage, category by category, at 1 h, 2 h, 4 h, 8 h, 24 h, 72 h and 168 h. Give each one in words, then on the scale: 1 none, 2 low, 3 medium, 4 high, 5 very high.

Heike Brodersen: Health of persons. In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h none.

Heike Brodersen: Impact health: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 1.

Heike Brodersen: Financial. In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h none.

Heike Brodersen: Impact financial: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 1.

Heike Brodersen: Legal. Regulations are breached. Breaches lead to considerable consequences, for example high fines. Breaches of contract lead to high contractual penalties or consequences. In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h low, 168 h high.

Heike Brodersen: Impact legal: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 2, 168 h 4.

Heike Brodersen: Image. Customers complain to the companies, and there are negative reports in supra-regional or national media and in social media; the fault lies outside. In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h low, 168 h low.

Heike Brodersen: Impact image: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 2, 168 h 2.

Heike Brodersen: Operational. In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h low, 168 h low.

Heike Brodersen: Impact operational: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 2, 168 h 2.

Franziska Dohm: How high is the potential threat, and what do you set for recovery?

Heike Brodersen: The potential threat is high. The one-off payments and salary transfers process has an RTO (recovery time objective) of more than 168 hours, because it was classed as not critical for short process outages. This is because the impacts of an outage in the various areas are classed as low, or as significant only after a longer period. Legally, breaches can occur if the process fails for longer than 72 hours. This means that legal consequences are classed as high only after three days. As for the company's image, it is expected that after 24 hours individual employees could complain. If the outage lasted a week, however, public press reports in the national media would be likely.

Heike Brodersen: RTO: 72 h.

Heike Brodersen: MTPD: >168 h.

Heike Brodersen: The process is relevant to the BCMS.

Franziska Dohm: What could make the process fail?

Heike Brodersen: Failure of SAP S/4HANA Finance; missing or wrong bank and payment data; failure of the connection to the bank; missing releases, or authorised signatories not available; failure of network, power supply or the HR master data system.

Franziska Dohm: And how do you run it in emergency operation?

Heike Brodersen: Emergency operation is restricted to salary payments that are due and to mandatory correction payments. Two qualified payroll clerks check recipient, bank details, amount, purpose of payment and release on the four-eyes principle. Payment orders are prepared in an encrypted template. Transmission follows once SAP S/4HANA Finance is restored, or goes through an emergency channel agreed beforehand with Finance and the bank. All payments are logged and reconciled in the system afterwards.

Franziska Dohm: Last, the resources the process needs.

Heike Brodersen: IT systems. HR master data system: RPO <1 h, RTO 72 h. Protection need: confidentiality very high; integrity very high; authenticity very high. Provides checked bank details, employment data and payment bases. Workaround: Bank details are taken from the protected digital personnel file and the last released master-data export. Changes are checked on the four-eyes principle.

Heike Brodersen: IT systems. SAP S/4HANA Finance: RPO <1 h, RTO 72 h. Protection need: confidentiality very high; integrity very high; authenticity very high. Records, checks, approves and transmits one-off payments for salaries and correction payments. Workaround: Payment orders are prepared in a released encrypted template. Transmission follows after restoration or goes through an emergency channel agreed with Finance and the bank.

Heike Brodersen: Technical resources. Corporate network: Enables protected access to HR and finance systems. Workaround: Access through an approved remote connection or an alternative company site.

Heike Brodersen: Technical resources. Power supply: Supplies workplaces, network components and end devices. Workaround: Use of a site that is not affected, or of secured remote workplaces.

Heike Brodersen: Roles. Payroll clerks: 70 in normal operation, 2 in emergency operation, needed within 72 h, remote or office. They create, check and monitor one-off payments and correction transfers. Workaround: Two qualified staff work only on deadline-critical payments.

Heike Brodersen: Sites. Central HR administration: The central seat of payroll. Workaround: Work from secured remote workplaces or an alternative company site.

Heike Brodersen: Depends on: HR master data system, SAP S/4HANA Finance, Corporate network, Power supply, Payroll clerks.

Franziska Dohm: Thank you.
