# Process map — Marschkamp

The processes of Marschkamp as the company's process identification lists them: 25 processes in three groups. The
number is the process map's own; the slug is the name the walk keys on. Twenty processes have a finished BIA record
and are walkable. Five HR processes have none: the process identification rated each of them not time-critical.

## 1. Core processes

| No. | Process | Slug | Walkable | Upstream | Downstream |
|---|---|---|---|---|---|
| 1.1 | Raw material procurement | `raw-material-procurement` | yes | none | Production and processing |
| 1.2 | Production and processing | `production-and-processing` | yes | Raw material procurement | Order picking |
| 1.3 | Order picking | `order-picking` | yes | Production and processing | Goods dispatch and delivery |
| 1.4 | Goods dispatch and delivery | `dispatch-and-delivery` | yes | Order picking | none |
| 1.5 | Returns and animal by-product disposal | `returns-and-by-product-disposal` | yes | none | none |

Upstream and downstream are as each process's BIA record states them in its master data. The HR and IT records state none; the four HR and IT cells filled come from the process descriptions below (2.5, 3.6).

**1.1 Raw material procurement.** The process starts with determining demand from the production plan, the stock on
hand and the expected sales volumes. Purchasing selects approved suppliers, orders the meat and raw materials needed,
and monitors delivery quantity, delivery date and quality. The suppliers transport the goods to the production sites
in compliance with the prescribed cold chain. The process ends with the handover of the goods to goods receipt.

**1.2 Production and processing.** The process starts with taking over and checking the delivered raw materials.
After quality control and release, the raw materials are cut, processed and portioned according to the production
orders. The products are then packed, labelled and handed over to the chilled or intermediate storage area.

**1.3 Order picking.** The process covers assembling the produced and bought-in goods exactly per order and per
customer. The products are weighed, checked and assigned to their delivery orders, then made ready for loading.

**1.4 Goods dispatch and delivery.** The process starts with taking over the goods made ready by order picking. The
goods are loaded onto refrigerated vehicles and, on the basis of the transport plan, delivered to customers, regional
distribution centres and retail locations. Keeping the cold chain and documenting the handover of goods are part of
the process.

**1.5 Returns and animal by-product disposal.** The process covers taking back food that was complained about, is no
longer fit for sale or is left over, and animal by-products. The materials are collected in designated, labelled
containers, transported to the company's sites and stored separately until an approved disposal partner collects
them. Handover and disposal are documented traceably.

## 2. HR support processes

| No. | Process | Slug | Walkable | Upstream | Downstream |
|---|---|---|---|---|---|
| 2.1 | Payroll | `payroll` | yes | Time recording | not stated |
| 2.2 | One-off payments and salary transfers | `payments-and-salary-transfers` | yes | not stated | not stated |
| 2.3 | HR service ticketing | `hr-service-ticketing` | yes | not stated | not stated |
| 2.4 | Employee registration and deregistration | `employee-registration` | yes | not stated | not stated |
| 2.5 | Time recording | `time-recording` | yes | not stated | Payroll |
| 2.6 | HR correspondence and documents | `hr-correspondence` | yes | not stated | not stated |
| 2.7 | Archiving of personnel records | `personnel-records-archiving` | no | not stated | not stated |
| 2.8 | Authority reporting and HR year-end work | `authority-reporting-and-year-end` | no | not stated | not stated |
| 2.9 | Decentralised employee capture | `decentralised-employee-capture` | no | not stated | not stated |
| 2.10 | Electronic social-insurance notifications | `social-insurance-notifications` | no | not stated | not stated |
| 2.11 | Recruiting | `recruiting` | no | not stated | not stated |

**2.1 Payroll.** The process covers creating new employees in the personnel administration system, maintaining the
personnel master data and running the monthly payroll. Working-time, allowance, absence and other payroll-relevant
data are checked, processed and made available for payment and for further processing in accounting.

**2.2 One-off payments and salary transfers.** The process covers recording, checking, releasing and managing one-off
payments and salary transfers in the central finance system. Payment data are reconciled with the released payroll
data and transmitted on time to the commissioned bank.

**2.3 HR service ticketing.** The process governs the central recording, categorisation, prioritisation and handling
of personnel-related requests from the operating and administrative sites. Requests are assigned to the responsible
HR functions, handled and documented traceably until closed.

**2.4 Employee registration and deregistration.** The process covers the administrative and statutory registration
and deregistration of employees. New employment relationships are recorded in the relevant internal systems and
reported on time to the competent bodies. When employees leave, the required deregistrations, system adjustments and
status checks are carried out.

**2.5 Time recording.** The process covers recording, checking, correcting and managing working times, in particular
attendance, shift times, overtime, absences and time corrections. The released time data are a basis for payroll and
for operational staff planning.

**2.6 HR correspondence and documents.** The process covers creating, editing and issuing standardised and individual
personnel documents, in particular employment contracts, contract changes, confirmations, letters on changes to the
employment relationship and other personnel-related correspondence.

**2.7 Archiving of personnel records.** The process covers the structured filing, retention and retrievability of
personnel records. Documents are managed in line with internal authorisation rules and statutory retention and
deletion periods. *The process was rated not time-critical in the underlying BIA.*

**2.8 Authority reporting and HR year-end work.** The process covers periodic and event-driven reports to authorities
and social-insurance bodies, and providing personnel-related data for the annual financial statements. *The process
was rated not time-critical in the underlying BIA.*

**2.9 Decentralised employee capture.** The process allows new employees to be recorded independently of location
with a standardised digital or paper capture form. The data collected are checked and then taken over into personnel
administration. *The process was rated not time-critical in the underlying BIA.*

**2.10 Electronic social-insurance notifications.** The process covers the electronic transmission of registrations,
deregistrations and other legally required employee data to the competent social-insurance body. *The process was
rated not time-critical in the underlying BIA.*

**2.11 Recruiting.** The process covers the staffing request, the job advertisement, application administration, the
selection of suitable candidates and the preparation of the hire. It ends with handing the required information over
to onboarding and personnel administration. *The process was rated not time-critical in the underlying BIA.*

## 3. IT support processes

| No. | Process | Slug | Walkable | Upstream | Downstream |
|---|---|---|---|---|---|
| 3.1 | Change and release management | `change-and-release-management` | yes | not stated | not stated |
| 3.2 | IT asset and configuration management | `asset-and-configuration-management` | yes | not stated | not stated |
| 3.3 | Incident and problem management | `incident-and-problem-management` | yes | IT event management | not stated |
| 3.4 | IT helpdesk and support | `helpdesk-and-support` | yes | not stated | not stated |
| 3.5 | Access management | `access-management` | yes | not stated | not stated |
| 3.6 | IT event management | `event-management` | yes | not stated | Incident and problem management |
| 3.7 | IT procurement and licence management | `it-procurement-and-licences` | yes | not stated | not stated |
| 3.8 | IT financial management | `it-financial-management` | yes | not stated | not stated |
| 3.9 | Data protection management | `data-protection` | yes | not stated | not stated |

**3.1 Change and release management.** The process covers planning, assessing, approving, steering and implementing
changes to IT systems, applications and infrastructure. Changes are moved into the production environment in a
controlled way, to reduce risk and keep the IT services stable.

**3.2 IT asset and configuration management.** The process covers the structured recording, management and control
of Marschkamp's IT assets and configuration items. Dependencies, states and changes are documented traceably over
the whole life cycle.

**3.3 Incident and problem management.** The process covers detecting, classifying, prioritising, handling and
resolving IT disruptions. Recurring or serious disruptions are analysed to identify their causes and to start lasting
corrective action. The aim is the rapid restoration and lasting stabilisation of the affected IT services.

**3.4 IT helpdesk and support.** The process is the central point of contact for IT disruptions and user requests.
Incoming reports are recorded, categorised, prioritised, handled or passed on to specialised support units. Progress
and resolution are documented in the central service management system.

**3.5 Access management.** The process covers requesting, checking, granting, changing, regularly reviewing and
withdrawing user authorisations. Access to systems, applications and data is managed on a role basis and according to
the defined security rules.

**3.6 IT event management.** The process covers the automated and manual monitoring of IT systems and IT services.
Technical events are recorded, filtered and assessed. Relevant deviations are passed on to incident management or the
responsible technical teams.

**3.7 IT procurement and licence management.** The process covers determining demand for, procuring and managing IT
hardware, software, licences and external IT services. Suppliers and offers are assessed, contracts and licence
holdings are managed, and compliance with internal procurement rules is monitored.

**3.8 IT financial management.** The process covers planning, steering and monitoring the IT budgets and IT costs. IT
spending, internal charging and the financial effects of IT projects and operations are recorded, analysed and
prepared for management.

**3.9 Data protection management.** The process covers the structured handling of data protection requests and data
protection incidents, and support for processing personal data lawfully. Data protection incidents are recorded,
assessed, documented and reported within the applicable deadlines to the competent internal and external bodies.
