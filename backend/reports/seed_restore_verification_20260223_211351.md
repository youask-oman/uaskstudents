# Seed Restore Verification Report

- Generated: 2026-02-23T21:13:51.3688706-08:00
- Throwaway DB: uask_db_seed_replay_verify
- Seed Replay: passed
- Verification Success: True
- Integrity Issues: PASS

## Key Row Counts

| Table | Count |
|---|---:|
| systemconfig | 56 |
| json_schemas | 4 |
| prompt_templates | 6 |
| prompt_bindings | 3 |
| providermodelpricing | 8 |
| credit_program_definition | 6 |
| plan | 6 |
| school | 117960 |
| internal users | 5 |
| credit_transfers | 0 |
| notifications | 0 |

## Forbidden Tables (must be 0)

- payment: 0
- invoice: 0
- subscription: 0
- chatsession: 0
- chatmessage: 0
- solveroutputattempt: 0
- billingledger: 0

## Artifacts

- Seed output: ackend/reports/seed_replay_seed_output.txt
- Verification output: ackend/reports/seed_replay_verify_output.txt
- JSON summary: $(Split-Path d:\uaskstudents\backend\reports\seed_restore_verification_20260223_211351.json -Leaf)

