# Admin Capability Matrix

- Total DB tables: **73**
- Admin nav links: **35**
- Admin API routes detected: **61**

## Priority Gaps To Add First

| Priority | Table | Why missing matters | Suggested tab |
|---|---|---|---|
| P1 | `canonicalproblem` | No canonical cache management visibility (keys, hit/miss, invalidations). | `/admin/cache/canonical` |
| P1 | `canonicalsolution` | No canonical solved-result cache inspection/invalidation. | `/admin/cache/canonical` |
| P1 | `llmusageledger` | No direct cost/tokens ledger explorer by request/user/model. | `/admin/observability/llm-usage` |
| P1 | `question_identity_cache` | No dedupe/identity cache visibility; hard to debug repetition logic. | `/admin/cache/question-identity` |
| P2 | `adminauditlog` | No first-class admin action audit trail page (who changed what). | `/admin/audit-log` |
| P2 | `invoicesequence` | No dedicated sequence health panel for invoice numbering. | `/admin/billing/invoice-sequence` |
| P2 | `schoolimportrun` | No import-run observability (status, counts, errors) for schools pipeline. | `/admin/data-imports/schools` |
| P2 | `seed_registry` | No seed execution/version visibility in admin. | `/admin/system/seeds` |
| P2 | `subscriptionbillinglink` | No direct mapping inspector between subscription records and billing entities. | `/admin/billing/subscription-links` |
| P2 | `subscriptionperiod` | No period-level subscription reconciliation panel. | `/admin/billing/subscription-periods` |
| P3 | `chateditcopy` | No admin diff/change history for edit mode copy. | `/admin/chat/edits` |
| P3 | `chateditcopyv2` | No admin diff/change history for edit mode v2 copy. | `/admin/chat/edits` |
| P3 | `chateditnotev2` | No admin annotations panel for edit v2. | `/admin/chat/edits` |
| P3 | `chatmessage` | Only implicit via chat pages; no admin moderation/search console. | `/admin/chat/operations` |
| P3 | `chatnote` | No admin notes dashboard for support workflow. | `/admin/chat/operations` |
| P3 | `chatsession` | No dedicated conversation operations console (lock, replay, archive). | `/admin/chat/operations` |
| P3 | `devicesignuplog` | No anti-abuse/signup-device analytics tab. | `/admin/security/signup-devices` |
| P3 | `followupchatturn` | No follow-up turn timeline inspector. | `/admin/chat/operations` |
| P3 | `solvesession` | No direct solve session operational table UI. | `/admin/solve/sessions` |
| P3 | `usersavedsolution` | No admin explorer for user-saved solutions. | `/admin/solve/saved-solutions` |

## Full Table Matrix

| Table | Control Level | Current Admin Surface | Gap | Priority |
|---|---|---|---|---|
| `canonicalproblem` | data_explorer_only | `/admin/data` | needs_tab | P1 |
| `canonicalsolution` | data_explorer_only | `/admin/data` | needs_tab | P1 |
| `llmusageledger` | data_explorer_only | `/admin/data` | needs_tab | P1 |
| `question_identity_cache` | data_explorer_only | `/admin/data` | needs_tab | P1 |
| `requestevent` | dedicated | `/admin/logs` | none | - |
| `adminauditlog` | data_explorer_only | `/admin/data` | needs_tab | P2 |
| `invoicesequence` | data_explorer_only | `/admin/data` | needs_tab | P2 |
| `schoolimportrun` | data_explorer_only | `/admin/data` | needs_tab | P2 |
| `seed_registry` | data_explorer_only | `/admin/data` | needs_tab | P2 |
| `subscriptionbillinglink` | data_explorer_only | `/admin/data` | needs_tab | P2 |
| `subscriptionperiod` | data_explorer_only | `/admin/data` | needs_tab | P2 |
| `chateditcopy` | data_explorer_only | `/admin/data` | needs_tab | P3 |
| `chateditcopyv2` | data_explorer_only | `/admin/data` | needs_tab | P3 |
| `chateditnotev2` | data_explorer_only | `/admin/data` | needs_tab | P3 |
| `chatmessage` | data_explorer_only | `/admin/data` | needs_tab | P3 |
| `chatnote` | data_explorer_only | `/admin/data` | needs_tab | P3 |
| `chatsession` | data_explorer_only | `/admin/data` | needs_tab | P3 |
| `devicesignuplog` | data_explorer_only | `/admin/data` | needs_tab | P3 |
| `followupchatturn` | data_explorer_only | `/admin/data` | needs_tab | P3 |
| `solvesession` | data_explorer_only | `/admin/data` | needs_tab | P3 |
| `usersavedsolution` | data_explorer_only | `/admin/data` | needs_tab | P3 |
| `adminnote` | dedicated | `/admin/users` | none | - |
| `billingledger` | dedicated | `/admin/billing/ledger` | none | - |
| `credithold` | dedicated | `/admin/billing/holds` | none | - |
| `creditlot` | dedicated | `/admin/users/{id}`, `/admin/billing/ledger` | none | - |
| `creditlotconsumption` | dedicated | `/admin/billing/ledger`, `/admin/users/{id}` | none | - |
| `creditprogramdefinition` | dedicated | `/admin/billing/programs` | none | - |
| `creditprogramenrollment` | dedicated | `/admin/billing/enrollments` | none | - |
| `creditprogramgrantlog` | dedicated | `/admin/users/{id}`, `/admin/billing/ledger` | none | - |
| `crop` | dedicated | `/admin/logs`, `/admin/data` | none | - |
| `invoice` | dedicated | `/admin/billing/invoices`, `/adminpayments?tab=invoices` | none | - |
| `invoicelineitem` | partial | `/adminpayments?tab=invoices` | acceptable_via_data_explorer | - |
| `json_schemas` | dedicated | `/admin/schema-registry` | none | - |
| `legal_acceptances` | dedicated | `/admin/legal/privacy-policy`, `/admin/legal/terms-of-service`, `/admin/users/{id}` | none | - |
| `legal_documents` | dedicated | `/admin/legal/privacy-policy`, `/admin/legal/terms-of-service` | none | - |
| `ocrartifact` | dedicated | `/admin/ocr-configuration` | none | - |
| `ocrauditevent` | dedicated | `/admin/ocr-configuration`, `/admin/social-logs` | none | - |
| `ocrcache` | dedicated | `/admin/ocr-configuration` | none | - |
| `ocrchoice` | dedicated | `/admin/ocr-configuration` | none | - |
| `ocrconfirmation` | dedicated | `/admin/ocr-configuration` | none | - |
| `ocrextractioncache` | dedicated | `/admin/ocr-configuration` | none | - |
| `ocrfigure` | dedicated | `/admin/ocr-configuration` | none | - |
| `ocrjob` | dedicated | `/admin/ocr-configuration`, `/admin/jobs` | none | - |
| `ocrquestion` | dedicated | `/admin/ocr-configuration` | none | - |
| `payment` | dedicated | `/adminpayments`, `/admin/legacy/payments` | none | - |
| `plan` | dedicated | `/admin/legacy/plans`, `/admin/legacy/subscriptions` | none | - |
| `promocode` | dedicated | `/admin/promo-codes` | none | - |
| `prompt_bindings` | dedicated | `/admin/prompt-bindings` | none | - |
| `prompt_templates` | dedicated | `/admin/prompt-registry`, `/admin/prompts` | none | - |
| `providermodelpricing` | dedicated | `/admin/billing/pricing` | none | - |
| `providerpricingauditevent` | dedicated | `/admin/billing/pricing` | none | - |
| `reconciliationfinding` | dedicated | `/admin/billing/health`, `/adminpayments?tab=reconciliation` | none | - |
| `reconciliationrecord` | dedicated | `/admin/billing/health`, `/adminpayments?tab=reconciliation` | none | - |
| `school` | data_explorer_only | `/admin/data` | acceptable_via_data_explorer | - |
| `solveroutputattempt` | dedicated | `/admin/solver-attempts` | none | - |
| `stripeevent` | partial | `/adminpayments?tab=stripe_events` | acceptable_via_data_explorer | - |
| `stripepricemap` | partial | `/adminpayments?tab=pricing`, `/adminpayments/config` | acceptable_via_data_explorer | - |
| `subscription` | dedicated | `/admin/legacy/subscriptions`, `/admin/users` | none | - |
| `systemconfig` | dedicated | `/admin/system-config`, `/admin/billing`, `/adminpayments/config` | none | - |
| `systemconfigversion` | dedicated | `/admin/system-config` | none | - |
| `systemerrorentry` | dedicated | `/admin/logs`, `/admin/dashboard` | none | - |
| `topuporder` | partial | `/adminpayments?tab=requests`, `/adminpayments/topups` | acceptable_via_data_explorer | - |
| `topupproduct` | dedicated | `/admin/billing/packs`, `/adminpayments?tab=pricing` | none | - |
| `upload` | dedicated | `/admin/logs`, `/admin/data` | none | - |
| `usageledger` | dedicated | `/admin/billing/ledger` | none | - |
| `usagelog` | dedicated | `/admin/dashboard`, `/admin/logs` | none | - |
| `user` | dedicated | `/admin/users` | none | - |
| `userquotaoverride` | dedicated | `/admin/quotas`, `/admin/users` | none | - |
| `voiceartifact` | dedicated | `/admin/logs` | none | - |
| `voiceaudio` | dedicated | `/admin/logs` | none | - |
| `voiceconfirmation` | dedicated | `/admin/logs` | none | - |
| `voicejob` | dedicated | `/admin/jobs` | none | - |
| `voicesession` | dedicated | `/admin/logs`, `/admin/users/{id}` | none | - |

## Confirmation Method

1. Regenerate this matrix after each migration and route change.
2. For each new table, require classification: `dedicated`, `partial`, or `data_explorer_only` with waiver.
3. Add CI check to fail if any new table is missing from matrix classification.
4. Keep admin route smoke (`admin_nav_manifest.json`) green on every deploy.