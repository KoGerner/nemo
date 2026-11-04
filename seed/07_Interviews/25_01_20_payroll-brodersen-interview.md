---
type: interview-transcript
company: Marschkamp Fleisch GmbH & Co. KG
synthetic: true
governance: D5-wholly-synthetic
department: payroll
unit: hr
interviewee: Heike Brodersen
owner: Heike Brodersen
facilitator: Franziska Dohm
date: 2025-01-20
covered: health, financial, legal, image, operational
source: prior BIA record 2.1
---

# Payroll BIA interview

**Date:** 20 January 2025, 10:00  
**Participants:** Heike Brodersen (Head of Payroll, process owner); Jan Thießen (Head of HR Systems); Franziska Dohm (BCM Officer, interviewer)  
**Record:** prior BIA record 2.1, Payroll. Synthetic demo data.

---

Franziska Dohm: Thank you for the time, Heike. First the process itself: what does it do, and where does it sit?

Heike Brodersen: The process covers creating new employees, the ongoing maintenance of payroll-relevant master data, processing working-time and pay data, and running and checking the monthly payroll. It is a support process, and its process owner is the head of payroll. The organisational unit is human resources.

Franziska Dohm: Then the impact of an outage, category by category, at 1 h, 2 h, 4 h, 8 h, 24 h, 72 h and 168 h. Give each one in words, then on the scale: 1 none, 2 low, 3 medium, 4 high, 5 very high.

Heike Brodersen: Health of persons. In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h none.

Heike Brodersen: Impact health: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 1.

Heike Brodersen: Financial. In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h none.

Heike Brodersen: Impact financial: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 1.

Heike Brodersen: Legal. From 24 hours there are low legal impacts, because payroll is delayed; from 72 hours high impacts, because statutory deadlines are exceeded; and from 168 hours very high impacts, because this can lead to considerable legal consequences and possible penalties. In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h low, 168 h high.

Heike Brodersen: Impact legal: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 2, 168 h 4.

Heike Brodersen: Image. From 72 hours there are high impacts on the image (internal and external), because the delay of payroll leads to a considerable loss of trust and to dissatisfaction among employees; and from 168 hours very high impacts, because this can lead to considerable reputational damage and a possible loss of business opportunities. In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h high.

Heike Brodersen: Impact image: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 4.

Heike Brodersen: Operational. From 2 hours there are low operational impacts, because accounting is still able to make short-term adjustments; from 8 hours medium impacts, because the delay considerably disrupts the accounting processes; and from 72 hours high impacts, because the missing transmission of the data carrier to the bank leads to considerable disruption and delay in financial transactions. In words: 1 h none, 2 h none, 4 h low, 8 h low, 24 h medium, 72 h medium, 168 h high.

Heike Brodersen: Impact operational: 1 h 1, 2 h 1, 4 h 2, 8 h 2, 24 h 3, 72 h 3, 168 h 4.

Franziska Dohm: How high is the potential threat, and what do you set for recovery?

Heike Brodersen: The potential threat is high. The payroll business process must not be interrupted for longer than 72 hours, because that would lead to considerable operational impacts. The main reason for this RTO of 72 hours is that the bank cannot transfer salaries if the data are not transmitted in time. On the transmission day the process may therefore not work for at most 72 hours before there are serious impacts on the processes that follow. It is therefore essential that this process is restored within 72 hours, to keep salary payments continuous.

Heike Brodersen: RTO: 72 h.

Heike Brodersen: MTPD: 168 h.

Heike Brodersen: The process is relevant to the BCMS.

Franziska Dohm: What could make the process fail?

Heike Brodersen: Failure of the payroll system or of the HR master data system; failure of the interface to financial accounting or to the payment system; missing or wrong time and master data; staff shortage in payroll or in HR system support; failure of network, power supply or remote access.

Franziska Dohm: And how do you run it in emergency operation?

Heike Brodersen: Emergency operation concentrates on on-time payroll, statutory notifications and critical corrections. Ten qualified payroll clerks and one HR systems owner work on prioritised cases. The basis is the last released data state, secured master-data exports and an encrypted list of differences for changes. Payment data are checked on the four-eyes principle. Mail and master-data changes that are not deadline-critical are collected and worked through after restoration.

Franziska Dohm: Last, the resources the process needs.

Heike Brodersen: Documents. Personnel mail: These include garnishments, notices of termination and other payroll-relevant documents. Workaround: Deadline-critical documents are prioritised, physically secured and worked through after restoration. Missing documents are requested specifically.

Heike Brodersen: IT systems. Payroll system: RPO <1 h, RTO 72 h. Protection need: confidentiality very high; integrity very high; authenticity very high. Processes payroll-relevant master data, time data, pay, deductions and payroll runs. Workaround: No complete manual substitute. The last secured data state is used; changes are recorded offline under control and entered after restoration.

Heike Brodersen: IT systems. HR master data system: RPO <1 h, RTO 72 h. Protection need: confidentiality very high; integrity very high; authenticity very high. Manages personal data, bank details, employment data and payroll-relevant master data. Workaround: Released master-data exports and secured personnel files are used. Changes are documented in an encrypted list of differences.

Heike Brodersen: IT systems. SAP S/4HANA Finance: RPO <1 h, RTO 72 h. Protection need: confidentiality very high; integrity very high; authenticity very high. Takes over checked payment data, supports releases and transmits bulk payments to the bank. Workaround: The released payment data carrier is recreated from the HR master data system. Releases are obtained through the defined emergency process.

Heike Brodersen: IT systems. HR-to-financial-accounting interface: RPO <1 h, RTO 72 h. Protection need: confidentiality very high; integrity very high; authenticity high. Transfers payroll data for posting and further processing in financial accounting. Workaround: Payroll and posting data are provided as a controlled file and imported, reconciled, once the interface is restored.

Heike Brodersen: Roles. Payroll clerks: 70 in normal operation, 10 in emergency operation, needed within 72 h, remote or office. They record and check payroll-relevant data and produce the monthly payroll. Workaround: A qualified staff pool works on prioritised payroll cases and critical corrections.

Heike Brodersen: Roles. HR systems owner: 2 in normal operation, 1 in emergency operation, needed within 72 h, remote or office. They monitor payroll runs, interfaces and technical jobs. Workaround: Mutual cover; if needed, the head of payroll takes over coordination.

Heike Brodersen: Roles. Head of Payroll: 1 in normal operation, 1 in emergency operation, needed within 72 h, remote or office. Responsible for prioritisation, control and formal releases. Workaround: Releases go through the documented deputy and emergency process.

Heike Brodersen: Sites. Central HR administration: The central workplace of payroll and HR administration. Workaround: The process can be continued from secured remote workplaces.

Heike Brodersen: Depends on: Personnel mail, Payroll system, HR master data system, SAP S/4HANA Finance, HR-to-financial-accounting interface, Payroll clerks, HR systems owner, Head of Payroll.

Franziska Dohm: Thank you.
