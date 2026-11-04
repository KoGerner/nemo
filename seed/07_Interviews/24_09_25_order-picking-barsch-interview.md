---
type: interview-transcript
company: Marschkamp Fleisch GmbH & Co. KG
synthetic: true
governance: D5-wholly-synthetic
department: order-picking
interviewee: Henning Barsch
owner: Henning Barsch
facilitator: Franziska Dohm
date: 2024-09-25
covered: health, financial, legal, image, operational
source: prior BIA record 1.3
---

# Order picking BIA interview

**Date:** 25 September 2024, 11:20  
**Participants:** Henning Barsch (Plant Manager, process owner); Sven Hollmann (Head of Order Picking); Dirk Wohlleben (Maintenance Manager); Franziska Dohm (BCM Officer, interviewer)  
**Record:** prior BIA record 1.3, Order picking. Synthetic demo data.

---

Franziska Dohm: Thank you for the time, Henning. First the process itself: what does it do, and where does it sit?

Henning Barsch: Order picking begins with weighing the ordered goods exactly per branch. After checking and release, the goods are made ready for the retail locations concerned and prepared for loading. It is a core process, and its process owner is plant management. Its upstream process is production and processing; the downstream process is goods dispatch and delivery.

Franziska Dohm: Then the impact of an outage, category by category, at 1 h, 2 h, 4 h, 8 h, 24 h, 72 h and 168 h. Give each one in words, then on the scale: 1 none, 2 low, 3 medium, 4 high, 5 very high.

Henning Barsch: Health of persons. A standstill causes no harm to persons. In words: 1 h –, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h none.

Henning Barsch: Impact health: 1 h –, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 1.

Henning Barsch: Financial. The delivered goods cannot be picked; they can be picked later. In words: 1 h –, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h none.

Henning Barsch: Impact financial: 1 h –, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 1.

Henning Barsch: Legal. There are no SLAs within the group. There are no defined quantities that have to be delivered either. In words: 1 h –, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h none.

Henning Barsch: Impact legal: 1 h –, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 1.

Henning Barsch: Image. There are several competitors in cutting and packing. In a standstill a substitute can be found, with the corresponding logistical and price problems. In words: 1 h –, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h none.

Henning Barsch: Impact image: 1 h –, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 1.

Henning Barsch: Operational. The damage is higher than with a production outage, because bought-in goods are added. The critical threshold of 72 h stays. In words: 1 h –, 2 h none, 4 h none, 8 h none, 24 h none, 72 h low, 168 h high.

Henning Barsch: Impact operational: 1 h –, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 2, 168 h 4.

Franziska Dohm: How high is the potential threat, and what do you set for recovery?

Henning Barsch: The potential threat is high. Order picking has an RTO (recovery time objective) of 72 hours, because a standstill after 72 hours has considerable operational impacts: bought-in goods are added, and the damage is higher than with an outage of production and processing. The financial impacts are low within the first 72 hours, but the delivered goods cannot be picked, which leads to picking them later. There are no defined quantities that have to be delivered within the group, and no service level agreements (SLAs), which means that the legal impacts are minimal within the first 72 hours. There are several competitors in cutting and packing. In a standstill a substitute can be found, but logistical and price problems can arise that become critical after 72 hours.

Henning Barsch: RTO: 72 h.

Henning Barsch: MTPD: >168 h.

Henning Barsch: The process is relevant to the BCMS.

Franziska Dohm: What could make the process fail?

Henning Barsch: Failure of the order-picking ERP or of the warehouse control; failure of refrigeration or a lack of storage capacity; staff shortage in order picking or engineering; missing order, merchandise-management or labelling data; blocked movement of goods between production, warehouse and loading.

Franziska Dohm: And how do you run it in emergency operation?

Henning Barsch: Order picking gives priority to the core ranges that matter for delivery and to goods already produced. Minimum operation runs with 15 staff and four technicians on site. If a site-specific system fails, work moves to the other site as far as capacity is available there. With reduced chilled space, goods are loaded straight into pre-cooled refrigerated vehicles. Deviations are documented by hand.

Franziska Dohm: Last, the resources the process needs.

Henning Barsch: IT systems. Microsoft Teams: RPO <24 h, RTO 72 h. Protection need: confidentiality medium; integrity medium; authenticity medium. Microsoft Teams is used for chat and video conferences. Workaround: Production can run without MS Teams too.

Henning Barsch: IT systems. Microsoft 365: RPO <24 h, RTO 72 h. Protection need: confidentiality medium; integrity medium; authenticity medium. Office 365 is needed as the standard resource for Word, Excel, PowerPoint, Outlook, OneDrive and Teams. Workaround: Production can run without Office 365 too.

Henning Barsch: IT systems. Atlassian Jira: RPO <24 h, RTO 72 h. Protection need: confidentiality medium; integrity medium; authenticity medium. Workaround: Production can run without JIRA too.

Henning Barsch: IT systems. CSB ERP Marschkamp: RPO <24 h, RTO 72 h. Protection need: confidentiality high (restricted business data); integrity medium (no influence on order picking); authenticity medium (order picking). The program is essential for production at the Marschkamp site. Workaround: none; the program is essential for order picking.

Henning Barsch: IT systems. MAWI ERP Breitenburg: RPO <24 h, RTO 72 h. Protection need: confidentiality high (restricted business data); integrity medium (no influence on order picking); authenticity medium (no influence on order picking). The program is essential for production at the Breitenburg site. Workaround: none; the program is essential for order picking.

Henning Barsch: IT systems. Merchandise management and price-labelling system: RPO <24 h, RTO 72 h. Protection need: confidentiality high (restricted permissions); integrity medium (wrong data are recognisable and easily corrected); authenticity medium (wrong data are recognisable and easily corrected). The data needed for price labelling are read out of the merchandise management system. Workaround: Price labelling is only possible with the merchandise management system; order picking is possible without an order too.

Henning Barsch: IT systems. Time-recording system: RPO <24 h, RTO 72 h. Protection need: confidentiality high; integrity high; authenticity high. This system serves only to record working times. No holiday or salary data are recorded. Workaround: Production can run without the time-recording system too.

Henning Barsch: IT systems. Microsoft SharePoint Online: RPO <24 h, RTO 72 h. Protection need: confidentiality medium; integrity medium; authenticity medium. SharePoint is used to exchange and store data. Workaround: Production can run without SharePoint too.

Henning Barsch: IT systems. Automated warehouse control: RPO <24 h, RTO 72 h. Protection need: confidentiality high; integrity medium (wrong data are recognisable and easily corrected); authenticity medium (wrong data are recognisable and easily corrected). The program is essential for production at the Marschkamp site. Workaround: none for the Marschkamp site; the program is essential for order picking at the Marschkamp site; the Breitenburg site can go on picking.

Henning Barsch: Technical resources. Refrigeration: Refrigeration covers the chilled range of 4°. Workaround: Goods can be stacked straight into the lorry.

Henning Barsch: Roles. Production staff: 30 in normal operation, 15 in emergency operation, needed within 72 h, on site. The jobs cover taking deliveries, packing, order picking and making goods ready. Workaround: A pool of 30 people is available. In emergency operation 15 people are needed.

Henning Barsch: Roles. Technician: 8 in normal operation, 4 in emergency operation, needed within 72 h, on site. The jobs cover solving technical problems when faults occur. Workaround: A pool of 8 people is available. In emergency operation 4 people are needed.

Henning Barsch: Roles. Order-picking supervisors: 2 in normal operation, 0 in emergency operation, needed within 72 h, on site. The order-picking supervisor leads and monitors the order-picking processes and coordinates the staff; in normal operation this takes 1 supervisor. Workaround: A pool of 2 people is available. Not needed in emergency operation.

Henning Barsch: Depends on: Microsoft Teams, Microsoft 365, Atlassian Jira, CSB ERP Marschkamp, MAWI ERP Breitenburg, Merchandise management and price-labelling system, Time-recording system, Microsoft SharePoint Online, Automated warehouse control, Refrigeration, Production staff, Technician, Order-picking supervisors.

Franziska Dohm: Thank you.
