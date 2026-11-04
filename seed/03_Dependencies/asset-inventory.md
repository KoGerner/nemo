# Asset inventory — Marschkamp

Every IT system, piece of equipment or facility, channel and role that the section-7 resource tables of Marschkamp's twenty
BIA records name, one row per distinct asset. The dependency register (`dependency-register.json`) holds the same
assets with each consuming process's own figures. RTO and RPO stand here only where every record that names the
asset gives the same value; where records differ, the register states each record's figure against its process.
Eight records carry no resource table (Employee registration and deregistration, Time recording, HR correspondence
and documents, HR service ticketing, IT asset and configuration management, IT event management, IT procurement and
licence management, IT financial management), so no record names them as a consumer. Each of them is linked,
written for the demo pack and marked so: four to an asset whose own description covers their work, and four (HR
service ticketing, IT asset and configuration management, IT event management, IT procurement and licence
management) by a plausible link the owner asked for, citing the process description and the asset's own. Such a
link carries no figure. Each of the eight names one position, written for the demo pack and marked so, held by a
name the organisation file gives.

## IT systems

| Asset ID | Name | Site | RTO | RPO | Used by |
|---|---|---|---|---|---|
| `microsoft-365` | Microsoft 365 | — | per process | per process | `raw-material-procurement`, `production-and-processing`, `order-picking`, `change-and-release-management`, `helpdesk-and-support`, `access-management`, `data-protection`, `hr-correspondence` (written for the demo pack), `hr-service-ticketing` (written for the demo pack), `it-procurement-and-licences` (written for the demo pack) |
| `microsoft-teams` | Microsoft Teams | — | per process | per process | `production-and-processing`, `order-picking`, `incident-and-problem-management`, `access-management`, `event-management` (written for the demo pack) |
| `sharepoint-online` | Microsoft SharePoint Online | — | 72 h | per process | `raw-material-procurement`, `production-and-processing`, `order-picking`, `data-protection`, `hr-correspondence` (written for the demo pack) |
| `jira` | Atlassian Jira | — | per process | <24 h | `production-and-processing`, `order-picking`, `change-and-release-management` |
| `jira-service-management` | Atlassian Jira Service Management | — | per process | per process | `incident-and-problem-management`, `helpdesk-and-support`, `access-management`, `data-protection`, `hr-service-ticketing` (written for the demo pack), `asset-and-configuration-management` (written for the demo pack), `event-management` (written for the demo pack) |
| `csb-erp-marschkamp` | CSB ERP Marschkamp | Marschkamp | 72 h | <24 h | `production-and-processing`, `order-picking`, `raw-material-procurement` (written for the demo pack), `dispatch-and-delivery` (written for the demo pack), `returns-and-by-product-disposal` (written for the demo pack) |
| `mawi-erp-breitenburg` | MAWI ERP Breitenburg | Breitenburg | 72 h | <24 h | `production-and-processing`, `order-picking`, `returns-and-by-product-disposal` (written for the demo pack) |
| `merchandise-and-price-labelling` | Merchandise management and price-labelling system | — | 72 h | <24 h | `production-and-processing`, `order-picking` |
| `time-recording-system` | Time-recording system | — | 72 h | <24 h | `production-and-processing`, `order-picking`, `time-recording` (written for the demo pack) |
| `automated-warehouse-control` | Automated warehouse control | Marschkamp | 72 h | <24 h | `production-and-processing`, `order-picking` |
| `payroll-system` | Payroll system | — | 72 h | <1 h | `payroll`, `payments-and-salary-transfers` (written for the demo pack), `employee-registration` (written for the demo pack) |
| `hr-master-data-system` | HR master data system | — | 72 h | <1 h | `payroll`, `payments-and-salary-transfers`, `employee-registration` (written for the demo pack), `hr-correspondence` (written for the demo pack) |
| `sap-s4hana-finance` | SAP S/4HANA Finance | — | 72 h | <1 h | `payroll`, `payments-and-salary-transfers`, `it-financial-management` (written for the demo pack), `it-procurement-and-licences` (written for the demo pack) |
| `hr-finance-interface` | HR-to-financial-accounting interface | — | 72 h | <1 h | `payroll` |
| `cisco-call-manager` | Cisco Call Manager | — | 8 h | >168 h | `incident-and-problem-management` |
| `cisco-telephony` | Cisco telephony | — | 8 h | <24 h | `helpdesk-and-support` |
| `bmc-remedy` | BMC Remedy AR System | — | 8 h | <1 h | `helpdesk-and-support` |
| `active-directory` | Microsoft Active Directory | — | 1 h | <1 h | `access-management`, `asset-and-configuration-management` (written for the demo pack) |
| `central-authorisation-system` | Central authorisation system | — | 1 h | <1 h | `access-management` |
| `keycloak` | Keycloak | — | 1 h | <1 h | `access-management` |

## IT infrastructure

| Asset ID | Name | Site | RTO | RPO | Used by |
|---|---|---|---|---|---|
| `corporate-network` | Corporate network | — | — | — | `payments-and-salary-transfers` |

## Equipment and facilities

| Asset ID | Name | Site | RTO | RPO | Used by |
|---|---|---|---|---|---|
| `price-labelling-devices` | Price-labelling devices | — | — | — | `production-and-processing`, `order-picking` (written for the demo pack) |
| `refrigeration` | Refrigeration | — | — | — | `production-and-processing`, `order-picking`, `raw-material-procurement` (written for the demo pack), `dispatch-and-delivery` (written for the demo pack), `returns-and-by-product-disposal` (written for the demo pack) |
| `vehicle-fleet` | Vehicle fleet | — | — | — | `dispatch-and-delivery`, `returns-and-by-product-disposal` |

## Utilities

| Asset ID | Name | Site | RTO | RPO | Used by |
|---|---|---|---|---|---|
| `power-supply` | Power supply | — | — | — | `payments-and-salary-transfers` |

## Communication channels

| Asset ID | Name | Site | RTO | RPO | Used by |
|---|---|---|---|---|---|
| `personnel-mail` | Personnel mail | Central HR administration | — | — | `payroll`, `hr-correspondence` (written for the demo pack) |

## Roles

| Asset ID | Role | Used by | Normal / emergency staff, provided within |
|---|---|---|---|
| `buyer` | Buyer | `raw-material-procurement` | 2 / 1, 72 h (Raw material procurement) |
| `cutting-staff` | Cutting staff | `production-and-processing` | 40 / 25, 72 h (Production and processing) |
| `production-staff` | Production staff | `production-and-processing`, `order-picking` | 40 / 25, 72 h (Production and processing); 30 / 15, 72 h (Order picking) |
| `technician` | Technician | `production-and-processing`, `order-picking` | 8 / 4, 72 h (Production and processing); 8 / 4, 72 h (Order picking) |
| `production-supervisors` | Production supervisors | `production-and-processing` | 3 / 1, 72 h (Production and processing) |
| `order-picking-supervisors` | Order-picking supervisors | `order-picking` | 2 / 0, 72 h (Order picking) |
| `fleet-staff` | Fleet staff | `dispatch-and-delivery`, `returns-and-by-product-disposal` | 15 / 10, 72 h (Goods dispatch and delivery); 15 / 10, 72 h (Returns and animal by-product disposal) |
| `fleet-supervisors` | Fleet supervisors | `dispatch-and-delivery` | 1 / 0, 72 h (Goods dispatch and delivery) |
| `payroll-clerks` | Payroll clerks | `payroll`, `payments-and-salary-transfers` | 70 / 10, 72 h (Payroll); 70 / 2, 72 h (One-off payments and salary transfers) |
| `hr-systems-owner` | HR systems owner | `payroll` | 2 / 1, 72 h (Payroll) |
| `head-of-payroll` | Head of Payroll | `payroll` | 1 / 1, 72 h (Payroll) |
| `release-manager` | Release manager | `change-and-release-management` | 2 / 1, >168 h (Change and release management) |
| `release-controller` | Release controller | `change-and-release-management` | 2 / 1, >168 h (Change and release management) |
| `recovery-team` | Recovery team | `incident-and-problem-management` | 500 / as needed, 8 h (Incident and problem management) |
| `lead-incident-manager` | Lead incident manager | `incident-and-problem-management` | 8 / 2, 8 h (Incident and problem management) |
| `manager-on-duty` | Manager on duty | `incident-and-problem-management` | 7 / 1, 8 h (Incident and problem management) |
| `it-helpdesk-staff` | IT helpdesk staff | `helpdesk-and-support` | 10 / 4, 8 h (IT helpdesk and support) |
| `windows-administrator` | Windows administrator | `access-management` | 30 / 1, 1 h (Access management) |
| `central-authorisation-administrator` | Central authorisation system administrator | `access-management` | 3 / 1, 1 h (Access management) |
| `keycloak-administrator` | Keycloak administrator | `access-management` | 5 / 1, 1 h (Access management) |
| `data-protection-officer` | Data protection officer | `data-protection` | 3 / 1, 72 h (Data protection management) |
| `data-protection-coordinator` | Data protection coordinator | `data-protection` | 4 / 1, 72 h (Data protection management) |

## External supply and backup equipment, written for the demo pack

Written for the demo pack, not in any prior record: no prior BIA record names these, so none carries a recovery
figure or a record reference. A backup is shown on the card it backs up, never as a dependency.

| Asset ID | Name | Type | Backup for |
|---|---|---|---|
| `grid-operator` | Grid operator | External supplier | — |
| `emergency-generator` | Emergency generator | Equipment and facilities | `power-supply` |
| `bank` | Bank | External supplier | — |

## Plant, utilities and approval, written for the demo pack

Written for the demo pack, not in any prior record: no prior BIA record names these. None carries a figure, a location or a record reference.

| Asset ID | Name | Type | Used by |
|---|---|---|---|
| `cutting-and-processing-lines` | Cutting and processing lines | Equipment and facilities | `production-and-processing` (written for the demo pack) |
| `steam-and-hot-water` | Steam and hot water | Utilities | `production-and-processing` (written for the demo pack) |
| `compressed-air` | Compressed air | Utilities | `production-and-processing` (written for the demo pack) |
| `mains-water` | Mains water | Utilities | `production-and-processing` (written for the demo pack) |
| `wastewater-treatment` | Wastewater treatment | Utilities | `production-and-processing` (written for the demo pack) |
| `industrial-gases` | Industrial gases (nitrogen, carbon dioxide) | Utilities | `production-and-processing` (written for the demo pack) |
| `veterinary-and-qa-release` | Veterinary and QA release | Approval | `production-and-processing` (written for the demo pack), `raw-material-procurement` (written for the demo pack), `order-picking` (written for the demo pack) |
| `cold-chain-temperature-monitoring` | Cold-chain temperature monitoring | Equipment and facilities | `raw-material-procurement` (written for the demo pack), `production-and-processing` (written for the demo pack), `order-picking` (written for the demo pack), `dispatch-and-delivery` (written for the demo pack), `returns-and-by-product-disposal` (written for the demo pack) |

## IT systems and sites, written for the demo pack

Written for the demo pack, not in any prior record: no prior BIA record names these IT systems; each rests on a
cause its user's record names in section 5. None carries a figure. The sites are the four of the company profile
(section 5), and Central HR administration, which prior BIA records 2.1 and 2.2 name as a site. A site row says
whether another site can take over: "partly" for production (prior BIA record 1.2), "yes" for one-off payments
(prior BIA record 2.2), and "not stated" everywhere else, a re-BIA question, never guessed.

| Asset ID | Name | Type | Site | Used by |
|---|---|---|---|---|
| `route-planner` | Route planner | IT system | Marschkamp logistics centre | `dispatch-and-delivery` (written for the demo pack) |
| `ticket-interface` | Ticket interface | IT system | — | `helpdesk-and-support` (written for the demo pack) |
| `remote-access` | Remote access | IT system | — | `payroll` (written for the demo pack) |
| `remote-maintenance-access` | Remote-maintenance access | IT system | — | `helpdesk-and-support` (written for the demo pack) |
| `network-and-system-monitoring` | Network and system monitoring | IT system | — | `event-management` (written for the demo pack), `incident-and-problem-management` (written for the demo pack) |
| `marschkamp-headquarters` | Marschkamp (headquarters) | Site | — | `production-and-processing` (takeover partly), `order-picking`, `dispatch-and-delivery`, `returns-and-by-product-disposal`, `raw-material-procurement`, `change-and-release-management`, `helpdesk-and-support`, `access-management`, `data-protection`, `incident-and-problem-management`, `it-financial-management`, `asset-and-configuration-management`, `event-management`, `it-procurement-and-licences` (written for the demo pack) |
| `marschkamp-logistics-centre` | Marschkamp logistics centre | Site | — | `dispatch-and-delivery` (written for the demo pack) |
| `wilstermarsch` | Wilstermarsch | Site | — | `production-and-processing` (takeover partly), `returns-and-by-product-disposal` (written for the demo pack) |
| `breitenburg` | Breitenburg | Site | — | `production-and-processing` (takeover partly), `order-picking`, `returns-and-by-product-disposal` (written for the demo pack) |
| `central-hr-administration` | Central HR administration | Site | — | `payroll` (prior BIA record 2.1), `payments-and-salary-transfers` (prior BIA record 2.2, takeover yes); `employee-registration`, `time-recording`, `hr-correspondence`, `hr-service-ticketing` (written for the demo pack) |

## External suppliers named in the records

The partners each record's own partner table names, as the record names them (one renamed: see what the
records leave open). They carry no recovery figure, because no record gives one.

| Asset ID | Name | Used by | Stated in |
|---|---|---|---|
| `raw-material-suppliers` | Raw material suppliers (framework contracts and the open market) | `raw-material-procurement`, `production-and-processing` (written for the demo pack) | prior BIA record 1.1 |
| `cleaning-contractors` | Cleaning contractors (Reinigung & Clar, Fresh & Clean) | `production-and-processing` | prior BIA record 1.2 |
| `external-technicians` | External technicians (Wirfixens GmbH, Technobros GmbH) | `production-and-processing` | prior BIA record 1.2 |
| `elbe-industrial-gases` | Elbe Industrial Gases GmbH | `production-and-processing` | prior BIA record 1.2 |
| `vehicle-workshops` | Vehicle workshops (internal and external) | `dispatch-and-delivery` | prior BIA record 1.4 |
| `schlugge-lagerlogistik` | Schlugge Lagerlogistik GmbH | `dispatch-and-delivery` | prior BIA record 1.4 |
| `muellnix` | Müllnix GmbH | `returns-and-by-product-disposal` | prior BIA record 1.5 |

## Suppliers and people written for the demo pack

Written for the demo pack, not in any prior record: no prior BIA record names these suppliers or functions. None carries a figure, a
location or a record reference. The functions are positions; each shows on the People line of the
activities it serves and never as a dependency. A service contractor is shown as a service mark on what
it services, never as a dependency. The supplier register in this folder lists every supplier, with
those that stand in the files only.

| Asset ID | Name | Type | Used by |
|---|---|---|---|
| `north-german-rendering` | North German Rendering GmbH | External supplier | `production-and-processing` |
| `frostmark-refrigeration` | Frostmark Refrigeration GmbH | External supplier | `refrigeration` (service mark on it) |
| `packform-north` | PackForm North GmbH | External supplier | `production-and-processing` |
| `north-gas` | North Gas GmbH | External supplier | `industrial-gases` (depends on it) |
| `north-net-communications` | North Net Communications GmbH | External supplier | `corporate-network` (depends on it) |
| `marsh-data-edi` | Marsh Data EDI Services GmbH | External supplier | `csb-erp-marschkamp` (depends on it), `mawi-erp-breitenburg` (depends on it) |
| `marshland-fuels` | Marshland Fuels GmbH | External supplier | `vehicle-fleet` (depends on it), `emergency-generator` (depends on it) |
| `steinburg-public-utilities` | Steinburg Public Utilities GmbH | External supplier | `mains-water` (depends on it), `wastewater-treatment` (depends on it) |
| `district-veterinary-office` | District Veterinary Office | External supplier | `veterinary-and-qa-release` (depends on it) |
| `social-insurance-agencies` | Social insurance agencies | External supplier | `employee-registration` |
| `stoer-valley-abattoir` | Stoer Valley Abattoir GmbH | External supplier | `raw-material-procurement`, `production-and-processing` |
| `kellinghusen-pork` | Kellinghusen Pork GmbH | External supplier | `raw-material-procurement`, `production-and-processing` |
| `north-crate-pool` | North Crate Pool GmbH | External supplier | `order-picking`, `dispatch-and-delivery`, `returns-and-by-product-disposal` |
| `crisis-team-lead` | Crisis team lead (deputy: Plant Manager) | Role | `raw-material-procurement`, `production-and-processing`, `order-picking`, `dispatch-and-delivery`, `returns-and-by-product-disposal` |
| `product-recall-coordinator` | Product recall and withdrawal coordinator | Role | `production-and-processing`, `returns-and-by-product-disposal` |
| `haccp-team-lead` | HACCP team lead | Role | `production-and-processing`, `order-picking`, `returns-and-by-product-disposal` |
| `site-management` | Site management (all three plants) | Role | `raw-material-procurement`, `production-and-processing`, `order-picking`, `dispatch-and-delivery`, `returns-and-by-product-disposal` |
| `shift-lead` | Shift lead (early, late, night sanitation, weekend) | Role | `production-and-processing`, `order-picking` |
| `refrigeration-engineer-on-call` | Refrigeration engineer on call (ammonia competence) | Role | `production-and-processing`, `order-picking`, `dispatch-and-delivery` |
| `works-council` | Works council (consent to overtime, shift changes, Sunday work) | Role | `raw-material-procurement`, `production-and-processing`, `order-picking`, `dispatch-and-delivery`, `returns-and-by-product-disposal` |
| `hr-service-coordinator` | HR service coordinator | Role | `hr-service-ticketing` |
| `senior-hr-administrator` | Senior HR administrator | Role | `employee-registration` |
| `time-management-coordinator` | Time management coordinator | Role | `time-recording` |
| `hr-document-manager` | HR document manager | Role | `hr-correspondence` |
| `configuration-manager` | Configuration manager | Role | `asset-and-configuration-management` |
| `it-monitoring-manager` | IT monitoring manager | Role | `event-management` |
| `licence-manager` | Licence manager | Role | `it-procurement-and-licences` |
| `it-controller` | IT controller | Role | `it-financial-management` |

## Dependencies between assets

One row per dependency a sentence states; the register holds the same edges as `depends_on`, with
the sentence beside them. No edge is inferred: none is written because two assets share a section,
and none to reach a wanted depth. A row stated in a prior BIA record is rendered the way the rest of
this seed renders the records, and the source's own wording stands in the record the reference
names. A row stated as authored for the pack was written for this demo pack and no prior record
states it; its words are that line of the resource dependencies file in the Prior Cycle folder,
word for word.

| Asset | Depends on | Stated in | The words |
|---|---|---|---|
| `corporate-network` | `power-supply` | prior BIA record 2.2 | Supplies workstations, network components and end devices. |
| `microsoft-365` | `corporate-network` | authored for the pack A1 | Microsoft 365 is reached over the Corporate network. |
| `microsoft-365` | `active-directory` | authored for the pack A2 | Microsoft 365 takes its user accounts from Microsoft Active Directory. |
| `microsoft-teams` | `microsoft-365` | authored for the pack A3 | Microsoft Teams runs as a service of Microsoft 365. |
| `microsoft-teams` | `corporate-network` | authored for the pack A4 | Microsoft Teams is reached over the Corporate network. |
| `sharepoint-online` | `microsoft-365` | authored for the pack A5 | Microsoft SharePoint Online runs as a service of Microsoft 365. |
| `sharepoint-online` | `corporate-network` | authored for the pack A6 | Microsoft SharePoint Online is reached over the Corporate network. |
| `jira` | `corporate-network` | authored for the pack A7 | Atlassian Jira is reached over the Corporate network. |
| `jira-service-management` | `corporate-network` | authored for the pack A8 | Atlassian Jira Service Management is reached over the Corporate network. |
| `csb-erp-marschkamp` | `corporate-network` | authored for the pack A9 | CSB ERP Marschkamp is reached over the Corporate network. |
| `mawi-erp-breitenburg` | `corporate-network` | authored for the pack A10 | MAWI ERP Breitenburg is reached over the Corporate network. |
| `merchandise-and-price-labelling` | `corporate-network` | authored for the pack A11 | The Merchandise management and price-labelling system is reached over the Corporate network. |
| `time-recording-system` | `corporate-network` | authored for the pack A12 | The Time-recording system is reached over the Corporate network. |
| `automated-warehouse-control` | `corporate-network` | authored for the pack A13 | Automated warehouse control is reached over the Corporate network. |
| `automated-warehouse-control` | `csb-erp-marschkamp` | authored for the pack A14 | Automated warehouse control takes its storage and retrieval orders from CSB ERP Marschkamp. |
| `payroll-system` | `corporate-network` | authored for the pack A15 | The Payroll system is reached over the Corporate network. |
| `payroll-system` | `hr-master-data-system` | authored for the pack A16 | The Payroll system takes payroll master data from the HR master data system. |
| `payroll-system` | `time-recording-system` | authored for the pack A17 | The Payroll system takes the recorded working times from the Time-recording system. |
| `hr-master-data-system` | `corporate-network` | authored for the pack A18 | The HR master data system is reached over the Corporate network. |
| `sap-s4hana-finance` | `corporate-network` | authored for the pack A19 | SAP S/4HANA Finance is reached over the Corporate network. |
| `hr-finance-interface` | `payroll-system` | authored for the pack A21 | The HR-to-financial-accounting interface takes the payroll data it transfers from the Payroll system. |
| `hr-finance-interface` | `corporate-network` | authored for the pack A22 | The HR-to-financial-accounting interface runs over the Corporate network. |
| `cisco-call-manager` | `corporate-network` | authored for the pack A23 | Cisco Call Manager carries its calls over the Corporate network. |
| `cisco-telephony` | `cisco-call-manager` | authored for the pack A24 | Cisco telephony runs on Cisco Call Manager as its call-control platform. |
| `cisco-telephony` | `corporate-network` | authored for the pack A25 | Cisco telephony is reached over the Corporate network. |
| `bmc-remedy` | `corporate-network` | authored for the pack A26 | BMC Remedy AR System is reached over the Corporate network. |
| `active-directory` | `corporate-network` | authored for the pack A27 | Microsoft Active Directory is reached over the Corporate network. |
| `central-authorisation-system` | `corporate-network` | authored for the pack A28 | The Central authorisation system is reached over the Corporate network. |
| `central-authorisation-system` | `active-directory` | authored for the pack A29 | The Central authorisation system takes the identities it assigns roles to from Microsoft Active Directory. |
| `keycloak` | `corporate-network` | authored for the pack A30 | Keycloak is reached over the Corporate network. |
| `keycloak` | `active-directory` | authored for the pack A31 | Keycloak takes its user identities from Microsoft Active Directory. |
| `price-labelling-devices` | `merchandise-and-price-labelling` | authored for the pack A32 | The Price-labelling devices take the data they print from the Merchandise management and price-labelling system. |
| `price-labelling-devices` | `power-supply` | authored for the pack A33 | The Price-labelling devices run on the Power supply. |
| `refrigeration` | `power-supply` | authored for the pack A34 | Refrigeration runs on the Power supply. |
| `power-supply` | `grid-operator` | authored for the pack A35 | The Power supply draws its electricity from the Grid operator. |
| `muellnix` | `north-german-rendering` | authored for the pack A39 | Müllnix GmbH passes the animal by-products it collects to North German Rendering GmbH for rendering. |
| `corporate-network` | `north-net-communications` | authored for the pack A41 | The Corporate network runs over lines from North Net Communications GmbH, the telecoms and network carrier. |
| `csb-erp-marschkamp` | `marsh-data-edi` | authored for the pack A42 | CSB ERP Marschkamp exchanges orders with the retail chains through Marsh Data EDI Services GmbH. |
| `mawi-erp-breitenburg` | `marsh-data-edi` | authored for the pack A43 | MAWI ERP Breitenburg exchanges orders with the retail chains through Marsh Data EDI Services GmbH. |
| `vehicle-fleet` | `marshland-fuels` | authored for the pack A44 | The Vehicle fleet runs on diesel from Marshland Fuels GmbH. |
| `emergency-generator` | `marshland-fuels` | authored for the pack A45 | The Emergency generator runs on diesel from Marshland Fuels GmbH. |
| `hr-finance-interface` | `sap-s4hana-finance` | authored for the pack A46 | The HR-to-financial-accounting interface delivers the payroll postings into SAP S/4HANA Finance. |
| `automated-warehouse-control` | `power-supply` | authored for the pack A47 | Automated warehouse control runs on the Power supply. |
| `cutting-and-processing-lines` | `power-supply` | authored for the pack A48 | Cutting and processing lines run on the Power supply. |
| `cutting-and-processing-lines` | `steam-and-hot-water` | authored for the pack A49 | Cutting and processing lines take steam and hot water from Steam and hot water. |
| `cutting-and-processing-lines` | `compressed-air` | authored for the pack A50 | Cutting and processing lines are driven by Compressed air. |
| `steam-and-hot-water` | `power-supply` | authored for the pack A51 | Steam and hot water runs on the Power supply. |
| `steam-and-hot-water` | `mains-water` | authored for the pack A52 | Steam and hot water takes its water from Mains water. |
| `compressed-air` | `power-supply` | authored for the pack A53 | Compressed air runs on the Power supply. |
| `mains-water` | `steinburg-public-utilities` | authored for the pack A54 | Mains water is supplied by Steinburg Public Utilities GmbH. |
| `wastewater-treatment` | `power-supply` | authored for the pack A55 | Wastewater treatment runs on the Power supply. |
| `wastewater-treatment` | `steinburg-public-utilities` | authored for the pack A56 | Wastewater treatment discharges through Steinburg Public Utilities GmbH. |
| `industrial-gases` | `north-gas` | authored for the pack A57 | Industrial gases (nitrogen, carbon dioxide) are supplied by North Gas GmbH. |
| `industrial-gases` | `elbe-industrial-gases` | authored for the pack A58 | Industrial gases (nitrogen, carbon dioxide) are supplied by Elbe Industrial Gases GmbH. |
| `veterinary-and-qa-release` | `district-veterinary-office` | authored for the pack A59 | Veterinary and QA release is granted by the District Veterinary Office. |
| `route-planner` | `corporate-network` | authored for the pack A60 | The Route planner is reached over the Corporate network. |
| `route-planner` | `csb-erp-marschkamp` | authored for the pack A61 | The Route planner takes the orders to deliver from CSB ERP Marschkamp. |
| `route-planner` | `marsh-data-edi` | authored for the pack A62 | The Route planner sends delivery notices through Marsh Data EDI Services GmbH. |
| `central-hr-administration` | `marschkamp-headquarters` | authored for the pack A63 | Central HR administration is at Marschkamp (headquarters). |
| `ticket-interface` | `bmc-remedy` | authored for the pack A64 | The Ticket interface takes tickets from BMC Remedy AR System. |
| `ticket-interface` | `jira-service-management` | authored for the pack A65 | The Ticket interface passes tickets to Atlassian Jira Service Management. |
| `remote-access` | `corporate-network` | authored for the pack A66 | Remote access is reached over the Corporate network. |
| `remote-maintenance-access` | `corporate-network` | authored for the pack A67 | Remote-maintenance access is reached over the Corporate network. |
| `remote-access` | `active-directory` | authored for the pack A68 | Remote access signs users in against Microsoft Active Directory. |
| `remote-maintenance-access` | `active-directory` | authored for the pack A69 | Remote-maintenance access signs helpdesk staff in against Microsoft Active Directory. |
| `jira-service-management` | `keycloak` | authored for the pack A70 | Atlassian Jira Service Management signs users in through Keycloak. |
| `jira` | `keycloak` | authored for the pack A71 | Atlassian Jira signs users in through Keycloak. |
| `network-and-system-monitoring` | `corporate-network` | authored for the pack A72 | Network and system monitoring watches the systems and links over the Corporate network. |
| `cold-chain-temperature-monitoring` | `power-supply` | authored for the pack A73 | Cold-chain temperature monitoring runs on the Power supply. |
| `cold-chain-temperature-monitoring` | `corporate-network` | authored for the pack A74 | Cold-chain temperature monitoring sends its temperature records over the Corporate network. |
| `time-recording-system` | `hr-master-data-system` | authored for the pack A75 | The Time-recording system takes the employees from the HR master data system. |
| `cutting-and-processing-lines` | `industrial-gases` | authored for the pack A76 | Cutting and processing lines take nitrogen and carbon dioxide from Industrial gases. |

## What the records leave open

- `microsoft-365`: RTO differs between records: 72 h (Raw material procurement); 72 h (Production and processing); 72 h (Order picking); >168 h (Change and release management); 8 h (IT helpdesk and support); 1 h (Access management); 72 h (Data protection management). Stated per consumer.
- `microsoft-365`: RPO differs between records: <24 h (Raw material procurement); <24 h (Production and processing); <24 h (Order picking); <24 h (Change and release management); <1 h (IT helpdesk and support); <1 h (Access management); <1 h (Data protection management). Stated per consumer.
- `microsoft-teams`: RTO differs between records: 72 h (Production and processing); 72 h (Order picking); 8 h (Incident and problem management); 1 h (Access management). Stated per consumer.
- `microsoft-teams`: RPO differs between records: <24 h (Production and processing); <24 h (Order picking); >168 h (Incident and problem management); <1 h (Access management). Stated per consumer.
- `sharepoint-online`: RPO differs between records: <168 h (Raw material procurement); <24 h (Production and processing); <24 h (Order picking); <1 h (Data protection management). Stated per consumer.
- `jira`: RTO differs between records: 72 h (Production and processing); 72 h (Order picking); >168 h (Change and release management). Stated per consumer.
- `jira-service-management`: Prior BIA record 3.4 names TicketME as its substitute system; TicketME is not a section-7 row in any record, so it is not an asset here.
- `jira-service-management`: RTO differs between records: 8 h (Incident and problem management); 8 h (IT helpdesk and support); 1 h (Access management); 72 h (Data protection management). Stated per consumer.
- `jira-service-management`: RPO differs between records: <24 h (Incident and problem management); <1 h (IT helpdesk and support); <1 h (Access management); <1 h (Data protection management). Stated per consumer.
- `automated-warehouse-control`: Prior BIA record 1.3: the description starts with unfilled template text ('What does the program do? What is it used for? (1 sentence)'); left out here.
- `refrigeration`: The records describe different scope: three zones, frozen, 4 °C and 10 °C (prior BIA record 1.2); the 4 °C chilled area (prior BIA record 1.3). No record says which site.
- `buyer`: Prior BIA record 1.1: the workaround names the stand-in as 'xxx', a placeholder the record never filled.
- `production-staff`: Pool and emergency headcount differ by record: 40 and 25 (prior BIA record 1.2), 30 and 15 (prior BIA record 1.3).
- `order-picking-supervisors`: Prior BIA record 1.3: normal headcount 2, but the description says 1 supervisor is needed in normal operation.
- `fleet-supervisors`: Prior BIA record 1.4: normal headcount 1, but the description is the production supervisors' text, which says 3 supervisors are needed in normal operation.
- `payroll-clerks`: re-BIA finding: prior BIA records 2.1 and 2.2 (§7.3) give 70 payroll clerks in normal operation, for a company of about 600 staff (01_Organisation/company-profile.md). The figure stands as the records give it; the re-BIA asks again.
- `recovery-team`: re-BIA finding: prior BIA record 3.3 (§7.2) gives a recovery team of 500 in normal operation, for a company of about 600 staff (01_Organisation/company-profile.md). The figure stands as the record gives it; the re-BIA asks again.
- `windows-administrator`: re-BIA finding: prior BIA record 3.5 (§7.2) gives 30 Windows administrators in normal operation, for a company of about 600 staff (01_Organisation/company-profile.md). The figure stands as the record gives it; the re-BIA asks again.
- `elbe-industrial-gases`: Prior BIA record 1.2 names a real brand here; renamed for the demo pack on the owner's ruling (ADR-0034). The register's quality flag on this asset keeps the record's own word.
- `schlugge-lagerlogistik`: Prior BIA record 1.4 leaves what this firm covers as 'xxx', a placeholder the record never filled.

Every asset carries an owner written for the demo pack, except six left open on purpose, each with its reason.
