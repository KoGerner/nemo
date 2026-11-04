---
type: interview-transcript
company: Marschkamp Fleisch GmbH & Co. KG
synthetic: true
governance: D5-wholly-synthetic
department: production-and-processing
interviewee: Henning Barsch
owner: Henning Barsch
facilitator: Franziska Dohm
date: 2024-09-24
covered: health, financial, legal, image, operational
source: prior BIA record 1.2
---

# Production and processing BIA interview

**Date:** 24 September 2024, 15:23  
**Participants:** Henning Barsch (Plant Manager, process owner); Petra Louven (Head of Production); Dirk Wohlleben (Maintenance Manager); Franziska Dohm (BCM Officer, interviewer)  
**Record:** prior BIA record 1.2, Production and processing. Synthetic demo data.

---

Franziska Dohm: Thank you for the time, Henning. First the process itself: what does it do, and where does it sit?

Henning Barsch: The process begins with taking over the goods: the delivered raw materials are carefully checked and accepted. After checking and release, the raw materials are cut into their parts. Several processing steps follow, in which the parts are divided into the portions wanted. After portioning, the products are packed and moved to storage. It is a core process, and its process owner is plant management. Its upstream process is raw material procurement; the downstream process is order picking.

Franziska Dohm: Then the impact of an outage, category by category, at 1 h, 2 h, 4 h, 8 h, 24 h, 72 h and 168 h. Give each one in words, then on the scale: 1 none, 2 low, 3 medium, 4 high, 5 very high.

Henning Barsch: Health of persons. A production standstill cannot cause harm to persons. In words: 1 h –, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h none.

Henning Barsch: Impact health: 1 h –, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 1.

Henning Barsch: Financial. Delivered goods can always be frozen, put into storage or sold. New goods are no longer delivered. In words: 1 h –, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h none.

Henning Barsch: Impact financial: 1 h –, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 1.

Henning Barsch: Legal. There are no SLAs within the group. There are no defined quantities that have to be delivered either. In words: 1 h –, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h none.

Henning Barsch: Impact legal: 1 h –, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 1.

Henning Barsch: Image. There are several competitors in cutting and packing. In a standstill a substitute can be found, with the corresponding logistical and price problems. In words: 1 h –, 2 h none, 4 h none, 8 h none, 24 h none, 72 h none, 168 h none.

Henning Barsch: Impact image: 1 h –, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 1, 168 h 1.

Henning Barsch: Operational. Everything up to 24 h can be made up (with extra effort). After 72 h high losses of yield are to be expected. In words: 1 h –, 2 h none, 4 h none, 8 h none, 24 h none, 72 h low, 168 h high.

Henning Barsch: Impact operational: 1 h –, 2 h 1, 4 h 1, 8 h 1, 24 h 1, 72 h 2, 168 h 4.

Franziska Dohm: How high is the potential threat, and what do you set for recovery?

Henning Barsch: The potential threat is high. Setting a recovery time objective (RTO) of 72 hours for production and processing rests on several decisive factors. Operationally, a standstill of up to 24 hours can be compensated with extra effort. A standstill of more than 72 hours, however, would lead to considerable losses of yield.

Henning Barsch: RTO: 72 h.

Henning Barsch: MTPD: >168 h.

Henning Barsch: The process is not relevant to the BCMS.

Franziska Dohm: What could make the process fail?

Henning Barsch: Failure of essential production equipment; failure of the production ERP or of the warehouse control; power, refrigeration, water or compressed-air failure; missing raw materials or packaging materials; staff shortage in production, cutting, engineering or cleaning; quality or hygiene block on a production area.

Franziska Dohm: And how do you run it in emergency operation?

Henning Barsch: The production programme is reduced to prioritised articles and available lines. Available raw materials are frozen, put into intermediate storage, processed differently or sold on in a controlled way. Where technically possible, production is moved to another site. Minimum operation runs with 25 staff in production, 25 staff in cutting, four technicians and one supervisor. Administrative work that is not essential is suspended.

Franziska Dohm: Last, the resources the process needs.

Henning Barsch: IT systems. MAWI ERP Breitenburg: RPO <24 h, RTO 72 h. Protection need: confidentiality high (restricted business data); integrity medium (no influence on production); authenticity medium (no influence on production). The program is essential for production at the Breitenburg site. Workaround: none; the program is essential for production at the Breitenburg site.

Henning Barsch: IT systems. CSB ERP Marschkamp: RPO <24 h, RTO 72 h. Protection need: confidentiality high (restricted business data); integrity medium (no influence on production); authenticity medium (no influence on production). The program is essential for production at the Marschkamp site. Workaround: none; the program is essential for production at the Marschkamp site.

Henning Barsch: IT systems. Microsoft 365: RPO <24 h, RTO 72 h. Protection need: confidentiality medium; integrity medium; authenticity medium. Office 365 is needed as the standard resource for Word, Excel, PowerPoint, Outlook, OneDrive and Teams. Workaround: Production can run without Office 365 too.

Henning Barsch: IT systems. Microsoft Teams: RPO <24 h, RTO 72 h. Protection need: confidentiality medium; integrity medium; authenticity medium. Microsoft Teams is used for chat and video conferences. Workaround: Production can run without MS Teams too.

Henning Barsch: IT systems. Atlassian Jira: RPO <24 h, RTO 72 h. Protection need: confidentiality medium; integrity medium; authenticity medium. Workaround: Production can run without JIRA too.

Henning Barsch: IT systems. Merchandise management and price-labelling system: RPO <24 h, RTO 72 h. Protection need: confidentiality high (restricted permissions); integrity medium (wrong data are recognisable and easily corrected); authenticity medium (wrong data are recognisable and easily corrected). The data needed for price labelling are read out of the merchandise management system. Workaround: Price labelling is only possible with the merchandise management system; production is possible without an order too.

Henning Barsch: IT systems. Time-recording system: RPO <24 h, RTO 72 h. Protection need: confidentiality high; integrity high; authenticity high. This system serves only to record working times. No holiday or salary data are recorded. Workaround: Production can run without the time-recording system too.

Henning Barsch: IT systems. Microsoft SharePoint Online: RPO <24 h, RTO 72 h. Protection need: confidentiality medium; integrity medium; authenticity medium. SharePoint is used to exchange and store data. Workaround: Production can run without SharePoint too.

Henning Barsch: IT systems. Automated warehouse control: RPO <24 h, RTO 72 h. Protection need: confidentiality high (restricted business data); integrity medium (wrong data are recognisable and easily corrected); authenticity medium (wrong data are recognisable and easily corrected). Software of the automated high-bay warehouse. The program is essential for production at the Marschkamp site. Workaround: none for the Marschkamp site; the program is essential for production at the Marschkamp site; the Breitenburg site can go on producing.

Henning Barsch: Technical resources. Price-labelling devices: The price-labelling devices of the company of the same name are used for price labelling. Workaround: If price labelling fails there is no direct workaround, because several parallel lines are in use.

Henning Barsch: Technical resources. Refrigeration: Refrigeration covers three temperature ranges: deep-freeze, chilling at 4 degrees Celsius and chilling at 10 degrees Celsius. Workaround: If refrigeration is not available, the deep-freeze is kept up, while the chilled areas at 4° and 10° can be cleared.

Henning Barsch: Roles. Cutting staff: 40 in normal operation, 25 in emergency operation, needed within 72 h, on site. The job covers cutting and processing raw materials and meat products. Workaround: A pool of 40 people is available. In emergency operation 25 people are needed.

Henning Barsch: Roles. Production staff: 40 in normal operation, 25 in emergency operation, needed within 72 h, on site. The jobs cover taking deliveries, packing, order picking and making goods ready. Workaround: A pool of 40 people is available. In emergency operation 25 people are needed.

Henning Barsch: Roles. Technician: 8 in normal operation, 4 in emergency operation, needed within 72 h, on site. The jobs cover solving technical problems when faults occur. Workaround: A pool of 8 people is available. In emergency operation 4 people are needed.

Henning Barsch: Roles. Production supervisors: 3 in normal operation, 1 in emergency operation, needed within 72 h, on site. The production supervisor leads and monitors the production processes and coordinates the staff; in normal operation this takes 3 supervisors. Workaround: A pool of 3 people is available. Cover by delegating to a deputy or to the plant manager is possible. In emergency operation 1 production supervisor is needed.

Henning Barsch: Partners. Cleaning contractors: 2 suppliers (Reinigung & Clar, Fresh & Clean). Workaround: Possible under our own responsibility, and there are enough other service providers.

Henning Barsch: Partners. External technicians: Wirfixens GmbH, Technobros GmbH. Workaround: Well-known firms, assessed against criteria at regular intervals.

Henning Barsch: Partners. Elbe Industrial Gases GmbH: Supplier of nitrogen. Workaround: Other suppliers are available. A short-term switch is possible.

Henning Barsch: Depends on: MAWI ERP Breitenburg, CSB ERP Marschkamp, Microsoft 365, Microsoft Teams, Atlassian Jira, Merchandise management and price-labelling system, Time-recording system, Microsoft SharePoint Online, Automated warehouse control, Price-labelling devices, Refrigeration, Cutting staff, Production staff, Technician, Production supervisors.

Franziska Dohm: Thank you.
