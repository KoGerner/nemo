---
type: interview-transcript
company: Marschkamp Fleisch GmbH & Co. KG
synthetic: true
governance: D5-wholly-synthetic
department: incident-and-problem-management
unit: it
interviewee: Marek Sobotta
owner: Marek Sobotta
facilitator: Franziska Dohm
date: 2025-02-25
covered: health, financial, legal, image, operational
source: prior BIA record 3.3
---

# Incident and problem management BIA interview

**Date:** 25 February 2025, 11:50  
**Participants:** Marek Sobotta (Head of IT Operations, process owner); Tim Ohlsen (Lead Incident Manager); Franziska Dohm (BCM Officer, interviewer)  
**Record:** prior BIA record 3.3, Incident and problem management. Synthetic demo data.

---

Franziska Dohm: Thank you for the time, Marek. First the process itself: what does it do, and where does it sit?

Marek Sobotta: The systematic detection, classification, handling and resolution of IT faults, and identifying and removing the underlying causes of recurring faults, to ensure the availability and stability of IT services. It is a support process, and its process owner is the head of IT operations. The organisational unit is IT.

Franziska Dohm: Then the impact of an outage, category by category, at 1 h, 2 h, 4 h, 8 h, 24 h, 72 h and 168 h. Give each one in words, then on the scale: 1 none, 2 low, 3 medium, 4 high, 5 very high.

Marek Sobotta: Health of persons. In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h none.

Marek Sobotta: Impact health: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 1.

Marek Sobotta: Financial. In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h none.

Marek Sobotta: Impact financial: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 1.

Marek Sobotta: Legal. In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h low.

Marek Sobotta: Impact legal: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 2.

Marek Sobotta: Image. In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h none.

Marek Sobotta: Impact image: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 1.

Marek Sobotta: Operational. Assumption: a major incident (by definition business-critical) is not handled over the time span stated. In words: 1 h none, 2 h low, 4 h low, 8 h medium, 24 h high, 72 h very high, 168 h very high.

Marek Sobotta: Impact operational: 1 h 1, 2 h 2, 4 h 2, 8 h 3, 24 h 4, 72 h 5, 168 h 5.

Franziska Dohm: How high is the potential threat, and what do you set for recovery?

Marek Sobotta: The potential threat is very high. The recovery time was set at 8 h. What counts are the impacts shown in the criticality assessment, and the possibility of continuing the process in the emergency operation described until it is restored.

Marek Sobotta: RTO: 8 h.

Marek Sobotta: MTPD: 24 h.

Marek Sobotta: The process is relevant to the BCMS.

Franziska Dohm: What could make the process fail?

Marek Sobotta: Failure of the ticket system; failure of central communication or alerting channels; staff shortage in incident management or in the recovery teams; unclear service responsibility or missing escalation data; simultaneous major incidents competing for resources.

Franziska Dohm: And how do you run it in emergency operation?

Marek Sobotta: Major incidents are reported through defined emergency numbers. The lead incident manager and the manager on duty activate the recovery teams needed. Situation, decisions, measures, responsible people and timestamps are kept in a local incident log. Communication goes through available telephony, Microsoft Teams or the alerting system.

Franziska Dohm: Last, the resources the process needs.

Marek Sobotta: IT systems. Cisco Call Manager: RPO >168 h, RTO 8 h. Protection need: confidentiality low (the system mainly processes connection and contact data); integrity medium (wrong call forwarding can impair reachability); authenticity medium (calls and administrative changes must be reliably attributable). Cisco Call Manager provides the central telephony for reporting, escalating and coordinating IT faults. Workaround: Major-incident communication goes through mobile telephony, Microsoft Teams or the alerting system.

Marek Sobotta: IT systems. Microsoft Teams: RPO >168 h, RTO 8 h. Protection need: confidentiality medium (chats and meetings hold internal information on faults and recovery); integrity high (wrong situation information can lead to wrong decisions); authenticity high (contributions and decisions must be clearly attributable). Microsoft Teams is used for situation briefings, virtual war rooms and coordinating the recovery teams. Workaround: Communication goes by phone, e-mail and telephone conference. Decisions are documented in the incident log.

Marek Sobotta: IT systems. Atlassian Jira Service Management: RPO <24 h, RTO 8 h. Protection need: confidentiality medium (tickets hold internal technical and operational information); integrity high (priority, status, responsibility and timestamps must be correct); authenticity high (reports and handling steps must be traceably attributed). Atlassian Jira Service Management records, prioritises, assigns, escalates and documents incidents and problems. Workaround: Incidents are taken by phone or e-mail and kept in a local incident list with time, priority, responsibility and status.

Marek Sobotta: Roles. Recovery team: 500 in normal operation, as needed in emergency operation, needed within 8 h, on site or remote. Analyses faults and carries out technical recovery measures. Workaround: The specialist teams needed for the affected service are activated.

Marek Sobotta: Roles. Lead incident manager: 8 in normal operation, 2 in emergency operation, needed within 8 h, on site or remote. Leads major incidents, prioritises measures and coordinates communication and escalation. Workaround: Availability from a rotating staff pool.

Marek Sobotta: Roles. Manager on duty: 7 in normal operation, 1 in emergency operation, needed within 8 h, on site or remote. Takes cross-cutting decisions and ensures management escalations. Workaround: Cover by a named IT Operations manager.

Marek Sobotta: Depends on: Cisco Call Manager, Microsoft Teams, Atlassian Jira Service Management, Recovery team, Lead incident manager, Manager on duty.

Franziska Dohm: Thank you.
