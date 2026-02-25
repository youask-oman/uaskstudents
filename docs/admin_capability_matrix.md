# Admin Capability Matrix

Generated: 2026-02-25T22:20:18.449Z

| Capability | UI Tab | Route | Backend Endpoints | Permission/Role | Feature Flag | Status | Notes |
|---|---|---|---|---|---|---|---|
| Credits Overview | Credits Overview | `/admin/billing` | /api/v1/admin/credits/overview | admin | none | OK |  |
| Chat Billing | Chat Billing | `/admin/billing/chat-billing` | /api/v1/admin/observability/chat-billing | admin | none | OK |  |
| Enrollments | Enrollments | `/admin/billing/enrollments` | /api/admin/billing/programs/enrollments/all | admin | none | OK |  |
| Feature Flags | Feature Flags | `/admin/billing/flags` | /api/admin/billing/flags | admin | none | OK |  |
| Billing Health | Billing Health | `/admin/billing/health` | /api/admin/billing/health | admin | none | OK |  |
| Holds Monitor | Holds Monitor | `/admin/billing/holds` | /api/v1/admin/credits/holds | admin | none | OK |  |
| User Credit Inspector | User Credit Inspector | `/admin/billing/inspector` | /api/v1/admin/credits/overview | admin | none | OK |  |
| Invoices | Invoices | `/admin/billing/invoices` | /api/admin/billing/invoices | admin | none | OK |  |
| Usage Ledger | Usage Ledger | `/admin/billing/ledger` | /api/v1/admin/credits/ledger | admin | none | OK |  |
| /admin/billing/legacy | (excluded) | `/admin/billing/legacy` |  | admin | none | Intentionally Hidden | Legacy compatibility page; intentionally not in primary nav |
| Credit Packs | Credit Packs | `/admin/billing/packs` | /api/v1/admin/credits/packs | admin | none | OK |  |
| Model Pricing | Model Pricing | `/admin/billing/pricing` | /api/admin/billing/pricing | admin | none | OK |  |
| Credit Programs | Credit Programs | `/admin/billing/programs` | /api/admin/billing/programs | admin | none | OK |  |
| /admin/billing/programs/enrollments | (excluded) | `/admin/billing/programs/enrollments` |  | admin | none | Intentionally Hidden | Program-scoped enrollments detail route; primary entry is /admin/billing/enrollments |
| Refund Center | Refund Center | `/admin/billing/refunds` | /api/admin/billing/refunds | admin+ (refund execution may require elevated role) | none | OK |  |
| Top-Up Products | Top-Up Products | `/admin/billing/topup-products` | /api/admin/payments/pricing | superadmin (mutations), admin (read-only) | none | OK |  |
| /admin/billing/users/[userId]/wallet | (excluded) | `/admin/billing/users/[userId]/wallet` |  | admin | none | Intentionally Hidden | Context detail route reachable from billing inspector/ledger links |
| Canonical Cache | Canonical Cache | `/admin/cache/canonical` | /api/v1/admin/cache/canonical/problems<br/>/api/v1/admin/cache/canonical/solutions | admin | none | OK |  |
| Question Identity | Question Identity | `/admin/cache/question-identity` | /api/v1/admin/cache/question-identity | admin | none | OK |  |
| Credit Transfer Config | Credit Transfer Config | `/admin/config/credit_transfer` | /api/v1/admin/config/credit_transfer | admin | none | OK |  |
| Content | Content | `/admin/content` | /api/admin/content/concepts | admin | none | OK |  |
| Overview | Overview | `/admin/dashboard` | /api/v1/admin/stats/dashboard<br/>/api/v1/admin/analytics/overview | admin | none | OK |  |
| Data | Data | `/admin/data` | /api/admin/db/tables | admin | none | OK |  |
| Jobs & Workers | Jobs & Workers | `/admin/jobs` | /api/admin/jobs/status | admin | none | OK |  |
| /admin/legacy/payments | (excluded) | `/admin/legacy/payments` |  | admin | none | Intentionally Hidden | Deprecated legacy route kept for backward compatibility |
| /admin/legacy/plans | (excluded) | `/admin/legacy/plans` |  | admin | none | Intentionally Hidden | Deprecated legacy route kept for backward compatibility |
| /admin/legacy/subscriptions | (excluded) | `/admin/legacy/subscriptions` |  | admin | none | Intentionally Hidden | Deprecated legacy route kept for backward compatibility |
| Privacy Policy | Privacy Policy | `/admin/legal/privacy` | /api/legal/privacy | admin | none | OK |  |
| Terms of Service | Terms of Service | `/admin/legal/terms` | /api/legal/terms | admin | none | OK |  |
| Logs | Logs | `/admin/logs` | /api/v1/admin/solve-traces | admin | none | OK |  |
| LLM Usage | LLM Usage | `/admin/observability/llm-usage` | /api/v1/admin/observability/llm-usage | admin | none | OK |  |
| OCR Configuration | OCR Configuration | `/admin/ocr-configuration` | /api/admin/ocr-configuration | admin | none | OK |  |
| Promo Codes | Promo Codes | `/admin/promo-codes` | /api/admin/promo-codes | admin | none | OK |  |
| Prompt Binding Pricing | Prompt Binding Pricing | `/admin/prompt-bindings` | /api/v1/admin/prompt_bindings?scope=solve | admin | none | OK |  |
| Prompt Registry | Prompt Registry | `/admin/prompt-registry` | /api/v1/admin/prompt-registry/prompts | admin | none | OK |  |
| Prompts | Prompts | `/admin/prompts` | /api/v1/admin/prompt-registry/prompts | admin | none | OK |  |
| Quotas | Quotas | `/admin/quotas` | /api/v1/admin/quotas | admin | none | OK |  |
| Schema Registry | Schema Registry | `/admin/schema-registry` | /api/v1/admin/prompt-registry/schemas | admin | none | OK |  |
| Social Logs | Social Logs | `/admin/social-logs` | /api/admin/whatsapp/monitor | admin | none | OK |  |
| Solvers | Solvers | `/admin/solver-attempts` | /api/v1/admin/solver-output-attempts | admin | none | OK |  |
| Subscriptions | Subscriptions | `/admin/subscriptions` | /api/v1/admin/users | admin | none | OK |  |
| System Config | System Config | `/admin/system-config` | /api/v1/admin/system-config | admin | none | OK |  |
| Users | Users | `/admin/users` | /api/v1/admin/users | admin | none | OK |  |
| /admin/users/[id] | (excluded) | `/admin/users/[id]` |  | admin | none | Intentionally Hidden | Context detail route reachable from /admin/users |
| WhatsApp Abuse Ops | WhatsApp Abuse Ops | `/admin/whatsapp-abuse` | /api/admin/whatsapp/abuse/overview | admin | none | OK |  |
| WhatsApp Bot | WhatsApp Bot | `/admin/whatsapp-bot` | /api/admin/whatsapp/status | admin | none | OK |  |
| WhatsApp Monitor | WhatsApp Monitor | `/admin/whatsapp-monitor` | /api/admin/whatsapp/monitor | admin | none | OK |  |
