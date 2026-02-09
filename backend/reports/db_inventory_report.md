# Database Inventory Report

**Database:** `uask_db`
**Host:** `postgres:5432`
**Generated:** 2026-02-09 17:44:16 UTC

## Summary

- **Total Tables:** 67
- **Total Rows:** 142,268
- **Total Size:** 88.6 MB

### By Classification

| Classification | Tables | Rows |
|----------------|-------:|-----:|
| AUDIT_PROD | 9 | 1,141 |
| CONFIG_PROD | 2 | 25 |
| ESSENTIAL_PROD | 15 | 2,845 |
| OPERATIONAL_PROD | 40 | 1,382 |
| SEED_DATA | 1 | 136,875 |

## All Tables

| Schema | Table | Rows | Classification | Seeded | Origin | Description |
|--------|-------|-----:|----------------|--------|--------|-------------|
| public | adminauditlog | 0 | AUDIT_PROD | NO | SYSTEM_GENERATED | Adminauditlog table (12 columns) |
| public | adminnote | 0 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Adminnote table (5 columns) |
| public | alembic_version | 1 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Database migration version tracking |
| public | billingledger | 0 | AUDIT_PROD | NO | SYSTEM_GENERATED | Billingledger table (31 columns) |
| public | canonicalproblem | 0 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Canonicalproblem table (15 columns) |
| public | canonicalsolution | 0 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Canonicalsolution table (10 columns) |
| public | chatmessage | 521 | OPERATIONAL_PROD | NO | USER_GENERATED | Chatmessage table (13 columns) |
| public | chatsession | 270 | ESSENTIAL_PROD | NO | USER_GENERATED | Chatsession table (11 columns) |
| public | credithold | 0 | ESSENTIAL_PROD | NO | SYSTEM_GENERATED | Credithold table (10 columns) |
| public | creditlot | 617 | ESSENTIAL_PROD | NO | SYSTEM_GENERATED | Creditlot table (18 columns) |
| public | creditlotconsumption | 16 | ESSENTIAL_PROD | NO | SYSTEM_GENERATED | Creditlotconsumption table (10 columns) |
| public | creditprogramdefinition | 4 | ESSENTIAL_PROD | NO | SYSTEM_GENERATED | Creditprogramdefinition table (15 columns) |
| public | creditprogramenrollment | 556 | ESSENTIAL_PROD | NO | SYSTEM_GENERATED | Creditprogramenrollment table (10 columns) |
| public | creditprogramgrantlog | 556 | AUDIT_PROD | NO | SYSTEM_GENERATED | Creditprogramgrantlog table (9 columns) |
| public | crop | 0 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Crop table (8 columns) |
| public | devicesignuplog | 0 | AUDIT_PROD | NO | SYSTEM_GENERATED | Devicesignuplog table (4 columns) |
| public | followupchatturn | 0 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Followupchatturn table (8 columns) |
| public | invoice | 13 | ESSENTIAL_PROD | NO | EXTERNAL_PROVIDER | Generated invoices |
| public | invoicelineitem | 13 | OPERATIONAL_PROD | NO | EXTERNAL_PROVIDER | Invoicelineitem table (12 columns) |
| public | invoicesequence | 1 | OPERATIONAL_PROD | NO | EXTERNAL_PROVIDER | Invoicesequence table (3 columns) |
| public | json_schemas | 8 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Json Schemas table (8 columns) |
| public | llmusageledger | 0 | AUDIT_PROD | NO | SYSTEM_GENERATED | Llmusageledger table (12 columns) |
| public | ocrartifact | 0 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Ocrartifact table (21 columns) |
| public | ocrauditevent | 0 | AUDIT_PROD | NO | SYSTEM_GENERATED | Ocrauditevent table (15 columns) |
| public | ocrcache | 0 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Ocrcache table (8 columns) |
| public | ocrchoice | 0 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Ocrchoice table (4 columns) |
| public | ocrconfirmation | 0 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Ocrconfirmation table (8 columns) |
| public | ocrextractioncache | 1 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Ocrextractioncache table (8 columns) |
| public | ocrfigure | 0 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Ocrfigure table (6 columns) |
| public | ocrjob | 0 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Ocrjob table (12 columns) |
| public | ocrquestion | 0 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Ocrquestion table (8 columns) |
| public | payment | 10 | ESSENTIAL_PROD | NO | EXTERNAL_PROVIDER | Stripe payment transactions (top-ups) |
| public | plan | 4 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Plan table (12 columns) |
| public | promocode | 0 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Promocode table (9 columns) |
| public | prompt_bindings | 9 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Prompt Bindings table (25 columns) |
| public | prompt_templates | 8 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Prompt Templates table (11 columns) |
| public | providermodelpricing | 8 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Providermodelpricing table (13 columns) |
| public | providerpricingauditevent | 0 | AUDIT_PROD | NO | SYSTEM_GENERATED | Providerpricingauditevent table (8 columns) |
| public | question_identity_cache | 35 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Question Identity Cache table (10 columns) |
| public | reconciliationfinding | 0 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Reconciliationfinding table (11 columns) |
| public | reconciliationrecord | 0 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Reconciliationrecord table (8 columns) |
| public | requestevent | 218 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Requestevent table (27 columns) |
| public | school | 136,875 | SEED_DATA | YES | ADMIN_MANAGED | School/institution reference data |
| public | schoolimportrun | 0 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Schoolimportrun table (12 columns) |
| public | solveroutputattempt | 188 | ESSENTIAL_PROD | NO | USER_GENERATED | Solveroutputattempt table (37 columns) |
| public | solvesession | 0 | ESSENTIAL_PROD | NO | USER_GENERATED | Solvesession table (7 columns) |
| public | stripeevent | 0 | OPERATIONAL_PROD | NO | EXTERNAL_PROVIDER | Stripeevent table (11 columns) |
| public | stripepricemap | 0 | OPERATIONAL_PROD | NO | EXTERNAL_PROVIDER | Stripepricemap table (7 columns) |
| public | subscription | 556 | ESSENTIAL_PROD | NO | SYSTEM_GENERATED | User subscription records |
| public | subscriptionbillinglink | 3 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Subscriptionbillinglink table (12 columns) |
| public | subscriptionperiod | 533 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Subscriptionperiod table (8 columns) |
| public | systemconfig | 25 | CONFIG_PROD | NO | ADMIN_MANAGED | Systemconfig table (4 columns) |
| public | systemconfigversion | 0 | CONFIG_PROD | NO | ADMIN_MANAGED | Systemconfigversion table (9 columns) |
| public | systemerrorentry | 0 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Systemerrorentry table (15 columns) |
| public | topuporder | 7 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Topuporder table (13 columns) |
| public | topupproduct | 12 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Topupproduct table (7 columns) |
| public | upload | 0 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Upload table (6 columns) |
| public | usageledger | 443 | AUDIT_PROD | NO | SYSTEM_GENERATED | Usageledger table (8 columns) |
| public | usagelog | 142 | AUDIT_PROD | NO | SYSTEM_GENERATED | Usagelog table (5 columns) |
| public | user | 615 | ESSENTIAL_PROD | NO | USER_GENERATED | User accounts with credentials and profile data |
| public | userquotaoverride | 0 | ESSENTIAL_PROD | NO | USER_GENERATED | Userquotaoverride table (6 columns) |
| public | usersavedsolution | 0 | ESSENTIAL_PROD | NO | USER_GENERATED | Usersavedsolution table (5 columns) |
| public | voiceartifact | 0 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Voiceartifact table (11 columns) |
| public | voiceaudio | 0 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Voiceaudio table (7 columns) |
| public | voiceconfirmation | 0 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Voiceconfirmation table (8 columns) |
| public | voicejob | 0 | OPERATIONAL_PROD | NO | SYSTEM_GENERATED | Voicejob table (10 columns) |
| public | voicesession | 0 | ESSENTIAL_PROD | NO | USER_GENERATED | Voicesession table (6 columns) |

## Top 20 Largest Tables

| Table | Rows | Size | Classification |
|-------|-----:|------|----------------|
| school | 136,875 | 80.2 MB | SEED_DATA |
| creditlot | 617 | 344.0 KB | ESSENTIAL_PROD |
| user | 615 | 432.0 KB | ESSENTIAL_PROD |
| creditprogramenrollment | 556 | 224.0 KB | ESSENTIAL_PROD |
| creditprogramgrantlog | 556 | 280.0 KB | AUDIT_PROD |
| subscription | 556 | 136.0 KB | ESSENTIAL_PROD |
| subscriptionperiod | 533 | 264.0 KB | OPERATIONAL_PROD |
| chatmessage | 521 | 1.1 MB | OPERATIONAL_PROD |
| usageledger | 443 | 224.0 KB | AUDIT_PROD |
| chatsession | 270 | 120.0 KB | ESSENTIAL_PROD |
| requestevent | 218 | 328.0 KB | OPERATIONAL_PROD |
| solveroutputattempt | 188 | 1.6 MB | ESSENTIAL_PROD |
| usagelog | 142 | 80.0 KB | AUDIT_PROD |
| question_identity_cache | 35 | 224.0 KB | OPERATIONAL_PROD |
| systemconfig | 25 | 32.0 KB | CONFIG_PROD |
| creditlotconsumption | 16 | 128.0 KB | ESSENTIAL_PROD |
| invoice | 13 | 160.0 KB | ESSENTIAL_PROD |
| invoicelineitem | 13 | 48.0 KB | OPERATIONAL_PROD |
| topupproduct | 12 | 48.0 KB | OPERATIONAL_PROD |
| payment | 10 | 192.0 KB | ESSENTIAL_PROD |

## Tables with PII

| Table | PII Columns |
|-------|-------------|
| adminauditlog | ip_address |
| adminnote | admin_name |
| billingledger | token_usage_json, fee_tokens_applied |
| chatmessage | tokens_used |
| creditprogramdefinition | name |
| invoice | billing_address_json |
| llmusageledger | system_prompt_tokens, input_tokens, output_tokens, total_tokens |
| payment | ip_address |
| plan | name |
| prompt_bindings | max_output_tokens, retry_cap_tokens, max_input_tokens, system_schema_budget_tokens, context_budget_tokens, json_retry_max_output_tokens |
| requestevent | tokens_in, tokens_out, tokens_total |
| school | school_name, address_line1, full_address, street_name, csdname, normalized_name, normalized_address |
| solveroutputattempt | input_tokens, output_tokens, total_tokens, time_to_first_token_ms |
| topupproduct | name |
| usagelog | tokens_used |
| user | email, full_name, password_hash, tokens_used_this_month, last_token_reset, verification_token, ip_address, session_token, whatsapp_secret |
| userquotaoverride | token_limit |

## High Growth Tables (>100k rows)

| Table | Rows | Notes |
|-------|-----:|-------|
| school | 136,875 |  |

## Seed Sources

| Table | Seed File |
|-------|-----------|
| school | `scripts/seed_db.py` |

## Sanity Checks

- **Total tables found:** 67
- **Schemas included:** public
- **Excluded schemas:** pg_catalog, information_schema, pg_toast
