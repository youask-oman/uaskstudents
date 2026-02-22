# Database Configuration Values

## 1. Table: systemconfig
| KEY | VALUE | DESCRIPTION |
| :--- | :--- | :--- |
| tokens.ocr_image.extract_max | 1800 | Max tokens for OCR image extraction |
| tokens.ocr_image.input_max | 1400 | Max input tokens for OCR image solve |
| tokens.ocr_image.input_overhead | 350 | Input overhead tokens for OCR image solve |
| tokens.ocr_pdf.extract_max | 3200 | Max tokens for OCR PDF extraction |
| tokens.ocr_pdf.input_max | 1800 | Max input tokens for OCR PDF solve |
| tokens.ocr_pdf.input_overhead | 450 | Input overhead tokens for OCR PDF solve |
| tokens.ocr_v5.output_max | 800 | Max output tokens for OCR v5 |
| tokens.request.expected_output_budget | 1200 | Expected output tokens for request fit |
| tokens.request.system_and_schema_budget | 3500 | Estimated system+schema tokens |
| tokens.text.input_max | 1800 | Max input tokens for text solve |
| tokens.text.input_max_chars | 5500 | Max input characters for text solve |
| tokens.text.output_max_detailed_solve | 3000 | Max output tokens for detailed solve |
| tokens.text.output_max_detailed_study | 3500 | Max output tokens for detailed study |
| tokens.text.output_max_minimal_solve | 700 | Max output tokens for minimal solve |
| tokens.text.output_max_minimal_study | 1200 | Max output tokens for minimal study |
| tokens.text.output_retry_cap_detailed_solve | 3200 | Retry max output tokens for detailed solve |
| tokens.text.output_retry_cap_detailed_study | 3600 | Retry max output tokens for detailed study |
| tokens.voice.input_max | 1200 | Max input tokens for voice solve |
| tokens.voice.input_overhead | 150 | Input overhead tokens for voice solve |

## 2. Table: promptasset
| ID | KEY | KIND | PATH |
| :--- | :--- | :--- | :--- |
| 1 | shared:minimal_system | system | llm_profiles/shared/minimal_system.txt |
| 2 | shared:minimal_schema | schema | llm_profiles/shared/minimal_schema.json |
| 3 | shared:detailed_system | system | llm_profiles/shared/detailed_system.txt |
| 4 | shared:canonical_schema | schema | llm_profiles/shared/canonical_schema.json |
| 5 | free:system | system | llm_profiles/free/system.txt |
| 6 | free:schema | schema | llm_profiles/free/schema.json |

## 3. Table: plan
| ID | NAME | SLUG | FEATURES |
| :--- | :--- | :--- | :--- |
| 1 | Free | free | {'ocr_monthly_cap': 3, 'voice_monthly_cap': 3, 'daily_credit_cap': 5} |
| 2 | Student Standard | student_standard | {'ocr_monthly_cap': 100, 'voice_monthly_cap': 50, 'daily_credit_cap': 50} |
| 3 | Family Standard | family_standard | {'ocr_monthly_cap': 200, 'voice_monthly_cap': 100, 'daily_credit_cap': 100} |
| 4 | Enterprise | enterprise | {'ocr_monthly_cap': 500, 'voice_monthly_cap': 250, 'daily_credit_cap': 200} |

## 4. Table: planpromptlink
| ID | PLAN_ID | MODE | SYS_ID | SCH_ID |
| :--- | :--- | :--- | :--- | :--- |
| 1 | 1 | minimal | 5 | 6 |
| 2 | 2 | minimal | 1 | 2 |
| 3 | 2 | detailed | 3 | 4 |
| 4 | 3 | minimal | 1 | 2 |
| 5 | 3 | detailed | 3 | 4 |
