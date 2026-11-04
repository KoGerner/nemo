---
type: interview-transcript
company: Marschkamp Fleisch GmbH & Co. KG
synthetic: true
governance: D5-wholly-synthetic
department: helpdesk-and-support
unit: it
interviewee: Frerk Sievers
owner: Frerk Sievers
facilitator: Franziska Dohm
date: 2025-01-20
covered: health, financial, legal, image, operational
source: prior BIA record 3.4
---

# IT helpdesk and support BIA interview

**Date:** 20 January 2025, 13:09  
**Participants:** Frerk Sievers (Head of IT Helpdesk, process owner); Imke Schlüter (Service Desk Coordinator); Franziska Dohm (BCM Officer, interviewer)  
**Record:** prior BIA record 3.4, IT helpdesk and support. Synthetic demo data.

---

Franziska Dohm: Thank you for the time, Frerk. First the process itself: what does it do, and where does it sit?

Frerk Sievers: The process manages and resolves IT faults and user requests efficiently. It makes sure that every incoming request is recorded centrally, categorised and prioritised, so that it is handled quickly and effectively. The process also lets incidents be documented and followed up systematically, so that recurring problems are identified and long-term solutions are developed. It is a support process, and its process owner is the head of IT helpdesk. The organisational unit is IT.

Franziska Dohm: Then the impact of an outage, category by category, at 1 h, 2 h, 4 h, 8 h, 24 h, 72 h and 168 h. Give each one in words, then on the scale: 1 none, 2 low, 3 medium, 4 high, 5 very high.

Frerk Sievers: Health of persons. In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h none.

Frerk Sievers: Impact health: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 1.

Frerk Sievers: Financial. In words: 1 h none, 2 h medium, 4 h medium, 8 h medium, 24 h medium, 72 h medium, 168 h medium.

Frerk Sievers: Impact financial: 1 h 1, 2 h 3, 4 h 3, 8 h 3, 24 h 3, 72 h 3, 168 h 3.

Frerk Sievers: Legal. In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h none.

Frerk Sievers: Impact legal: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 1.

Frerk Sievers: Image. In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h none.

Frerk Sievers: Impact image: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 1.

Frerk Sievers: Operational. In words: 1 h none, 2 h low, 4 h low, 8 h medium, 24 h high, 72 h high, 168 h high.

Frerk Sievers: Impact operational: 1 h 1, 2 h 2, 4 h 2, 8 h 3, 24 h 4, 72 h 4, 168 h 4.

Franziska Dohm: How high is the potential threat, and what do you set for recovery?

Frerk Sievers: The potential threat is medium. The IT helpdesk and support process has an RTO of more than 168 hours, because financial and operational impacts of an outage are to be expected. Carrying out emergency measures, temporary solutions or the restoration of IT services can cause noticeable financial strain. Operational impacts are to be expected as well, because delays can occur in delivering important services.

Frerk Sievers: RTO: 8 h.

Frerk Sievers: MTPD: >168 h.

Frerk Sievers: The process is relevant to the BCMS.

Franziska Dohm: What could make the process fail?

Frerk Sievers: Failure of the telephony or of the ticket system; staff shortage in the service desk; overload from a sharply increased volume of requests; failure of the knowledge base or of the remote-maintenance access; disruption of the interface between the ticket systems.

Franziska Dohm: And how do you run it in emergency operation?

Frerk Sievers: The helpdesk restricts itself to business-critical faults and access problems. Requests are taken through an emergency number, company mobile phones or whichever ticket system is available. If no ticket system is available, the team keeps a local recording list with contact, service, priority, status and responsibility.

Franziska Dohm: Last, the resources the process needs.

Frerk Sievers: IT systems. Cisco telephony: RPO <24 h, RTO 8 h. Protection need: confidentiality medium (call and contact data are internal business data); integrity low (incorrect call data can be recognised and corrected); authenticity low (calls do not have to meet a high standard of proof). Cisco telephony provides the central telephone intake and forwarding of support requests. Workaround: Calls are diverted to company mobile phones or Microsoft Teams. An emergency number is communicated.

Frerk Sievers: IT systems. BMC Remedy AR System: RPO <1 h, RTO 8 h. Protection need: confidentiality medium (tickets hold internal technical and personal details); integrity medium (wrong priorities or status data impair the handling); authenticity medium (whoever created and whoever handled a ticket must be traceable). BMC Remedy AR System records, classifies, assigns and tracks support requests and faults. Workaround: Atlassian Jira Service Management is used as the substitute system. Basic information that was not transferred is documented in a local handover list.

Frerk Sievers: IT systems. Microsoft 365: RPO <1 h, RTO 8 h. Protection need: confidentiality medium (e-mails and files hold internal support information); integrity medium (incorrect information can be corrected from the ticket); authenticity medium (sender and handling must be traceable). Microsoft 365 is used for e-mail, knowledge documents, shift handovers and coordination in support. Workaround: Communication goes through Cisco telephony or company mobile phones. Requests are recorded in the available ticket system.

Frerk Sievers: IT systems. Atlassian Jira Service Management: RPO <1 h, RTO 8 h. Protection need: confidentiality medium (tickets hold internal technical and personal details); integrity medium (priority, status and solution must be documented correctly); authenticity medium (whoever created and whoever handled a ticket must be traceable). Atlassian Jira Service Management manages service requests and incidents and synchronises defined cases with TicketME. Workaround: TicketME is used as the substitute system. Missing details are documented in a local recording list.

Frerk Sievers: Roles. IT helpdesk staff: 10 in normal operation, 4 in emergency operation, needed within 8 h, remote or office. They take requests, prioritise them, carry out first analysis and escalate to the responsible support groups. Workaround: An available staff pool takes over telephony, ticket intake and first-line resolution.

Frerk Sievers: Depends on: Cisco telephony, BMC Remedy AR System, Microsoft 365, Atlassian Jira Service Management, IT helpdesk staff.

Franziska Dohm: Thank you.
