---
type: interview-transcript
company: Marschkamp Fleisch GmbH & Co. KG
synthetic: true
governance: D5-wholly-synthetic
department: access-management
unit: it
interviewee: Timo Voß
owner: Timo Voß
facilitator: Franziska Dohm
date: 2025-02-25
covered: health, financial, legal, image, operational
source: prior BIA record 3.5
---

# Access management BIA interview

**Date:** 25 February 2025, 12:59  
**Participants:** Timo Voß (Head of Identity and Access Management, process owner); Merle Asmussen (Senior Access Administrator); Franziska Dohm (BCM Officer, interviewer)  
**Record:** prior BIA record 3.5, Access management. Synthetic demo data.

---

Franziska Dohm: Thank you for the time, Timo. First the process itself: what does it do, and where does it sit?

Timo Voß: Managing and controlling user access to systems, applications and data, including granting, reviewing, changing and withdrawing permissions on the basis of defined security policies. It is a support process, and its process owner is the head of identity and access management. The organisational unit is IT.

Franziska Dohm: Then the impact of an outage, category by category, at 1 h, 2 h, 4 h, 8 h, 24 h, 72 h and 168 h. Give each one in words, then on the scale: 1 none, 2 low, 3 medium, 4 high, 5 very high.

Timo Voß: Health of persons. In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h none.

Timo Voß: Impact health: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 1.

Timo Voß: Financial. The possibility of causing very high damage with rights that still exist. In words: 1 h none, 2 h very high, 4 h very high, 8 h very high, 24 h very high, 72 h very high, 168 h very high.

Timo Voß: Impact financial: 1 h 1, 2 h 5, 4 h 5, 8 h 5, 24 h 5, 72 h 5, 168 h 5.

Timo Voß: Legal. In words: 1 h none, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h none.

Timo Voß: Impact legal: 1 h 1, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 1.

Timo Voß: Image. Repeated negative reports in local media or social media; the fault lies inside. In words: 1 h none, 2 h medium, 4 h medium, 8 h medium, 24 h medium, 72 h medium, 168 h medium.

Timo Voß: Impact image: 1 h 1, 2 h 3, 4 h 3, 8 h 3, 24 h 3, 72 h 3, 168 h 3.

Timo Voß: Operational. Noticeable impacts, delays in the flow and in delivering important services, with clear cuts in the quality, quantity and duration of the processes. In words: 1 h none, 2 h high, 4 h very high, 8 h very high, 24 h very high, 72 h very high, 168 h very high.

Timo Voß: Impact operational: 1 h 1, 2 h 4, 4 h 5, 8 h 5, 24 h 5, 72 h 5, 168 h 5.

Franziska Dohm: How high is the potential threat, and what do you set for recovery?

Timo Voß: The potential threat is very high. The recovery time was set at 1 h. What counts are the impacts shown in the criticality assessment, and the possibility of continuing the process in the emergency operation described until it is restored.

Timo Voß: RTO: 1 h.

Timo Voß: MTPD: 1 h.

Timo Voß: The process is relevant to the BCMS.

Franziska Dohm: What could make the process fail?

Timo Voß: Failure of an identity or authorisation system; compromise of administrative accounts; missing approvals or unclear role responsibility; staff shortage in the IAM team; faulty synchronisation between identity sources and target systems.

Franziska Dohm: And how do you run it in emergency operation?

Timo Voß: Priority goes to account locks, withdrawing privileged rights and the access the recovery teams need. Every change needs a traceable approval and is carried out on the four-eyes principle. If central IAM systems fail, prepared emergency accounts or direct changes in the target system are used. All measures are logged and cleaned up afterwards.

Franziska Dohm: Last, the resources the process needs.

Timo Voß: IT systems. Atlassian Jira Service Management: RPO <1 h, RTO 1 h. Protection need: confidentiality high (permission requests hold personal and security-relevant information); integrity high (request, approval and implementation status must be correct); authenticity high (those requesting, approving and carrying out must be clearly identified). Atlassian Jira Service Management steers the request, approval, implementation and evidence of permission changes. Workaround: Urgent locks are ordered by phone through a defined emergency number and documented in a four-eyes emergency form.

Timo Voß: IT systems. Microsoft 365: RPO <1 h, RTO 1 h. Protection need: confidentiality high (communication can hold personal and security-relevant details); integrity high (wrong details can lead to impermissible permissions); authenticity high (senders and approvals must be clearly traceable). Microsoft 365 supports communication, evidence of approvals and the secure provision of working documents. Workaround: For urgent locks, telephony and the local emergency form are used. Regular requests are held back until restoration.

Timo Voß: IT systems. Microsoft Teams: RPO <1 h, RTO 1 h. Protection need: confidentiality medium (chats can hold internal information on permission cases); integrity medium (chat content does not replace a formal approval); authenticity medium (participants must be traceable). Microsoft Teams is used for operational coordination in urgent permission cases. Workaround: Coordination goes by phone. Formal approvals are documented in the emergency form.

Timo Voß: IT systems. Microsoft Active Directory: RPO <1 h, RTO 1 h. Protection need: confidentiality very high (the directory holds identities, groups and administrative permissions); integrity very high (wrong identities or group memberships allow unauthorised access); authenticity very high (administrative changes must be clearly authenticated and logged). Microsoft Active Directory manages Windows identities, groups, device assignments and access rights. Workaround: Critical account locks are carried out through a separate administration account and an available domain controller. Changes are documented in the emergency log.

Timo Voß: IT systems. Central authorisation system: RPO <1 h, RTO 1 h. Protection need: confidentiality very high (the system holds role models and permission assignments for central applications); integrity very high (wrong roles can cause far-reaching unauthorised access); authenticity very high (approval and technical implementation must be attributable with proof). The central authorisation system manages role-based access and approval workflows for business applications. Workaround: Urgent withdrawals are made directly in the target systems by authorised administrators. Every measure is logged on the four-eyes principle.

Timo Voß: IT systems. Keycloak: RPO <1 h, RTO 1 h. Protection need: confidentiality very high (Keycloak processes identities, roles and login credentials); integrity very high (wrong roles or configurations can allow impermissible access); authenticity very high (authentication and administrative changes must be reliable). Keycloak provides central authentication and role-based authorisation for connected applications. Workaround: If it fails, critical applications are run through prepared local emergency accounts. Changes to emergency accounts are logged and cleaned up after restoration.

Timo Voß: Roles. Windows administrator: 30 in normal operation, 1 in emergency operation, needed within 1 h, remote or office. Carries out locks, unlocks and changes in Microsoft Active Directory. Workaround: Availability from a qualified pool of administrators.

Timo Voß: Roles. Central authorisation system administrator: 3 in normal operation, 1 in emergency operation, needed within 1 h, remote or office. Implements approved role and permission changes in the central authorisation system. Workaround: Cover from the qualified IAM team.

Timo Voß: Roles. Keycloak administrator: 5 in normal operation, 1 in emergency operation, needed within 1 h, remote or office. Manages realms, clients, roles and administrative emergency access in Keycloak. Workaround: Cover from the qualified IAM team.

Timo Voß: Depends on: Atlassian Jira Service Management, Microsoft 365, Microsoft Teams, Microsoft Active Directory, Central authorisation system, Keycloak, Windows administrator, Central authorisation system administrator, Keycloak administrator.

Franziska Dohm: Thank you.
