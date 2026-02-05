# 3-Tier Plotting Integration Test Report
Generated: 2026-02-04T17:00:32.789494
Problem: Solve for x, |2x - 3| = 7
Expected: x = -2 and x = 5

## Tier: FREE

### Solve Call
- Model: gpt-4o-mini
- System Prompt: global_system_prompt_v1
- Developer Prompt: solve_free_v1
- Schema: youask_math_solver_solve_free_minimal_v1.schema.json
- Request ID: chatcmpl-D5i0sx366jKNfTKPhqcSR3y0OPwAu
- Latency: 4163ms
- Tokens: 951 in / 176 out
- Success: True
- Final Answer: 

### Plot Trigger Call
- Developer Prompt: plot_trigger_v1
- Schema: youask_plot_trigger_v1.schema.json
- Request ID: None
- Latency: 0ms
- Tokens: 0 in / 0 out
- Success: False

### Summary
- Plot Generated: False
- Plot ID: None
- Errors: ['Unexpected answer: ', 'Trigger failed: No active prompt binding found for tier=FREE mode=PLOT_TRIGGER.']

## Tier: STANDARD

### Solve Call
- Model: gpt-4o-mini
- System Prompt: global_system_prompt_v1
- Developer Prompt: solve_standard_v1
- Schema: youask_math_solver_solve_standard_detailed_v1.schema.json
- Request ID: None
- Latency: 5910ms
- Tokens: 0 in / 0 out
- Success: False
- Final Answer: 

### Summary
- Plot Generated: False
- Plot ID: None
- Errors: ['Solve failed: Invalid \\escape: line 1 column 336 (char 335)']

## Tier: RESEARCH

### Solve Call
- Model: gpt-4o-mini
- System Prompt: global_system_prompt_v1
- Developer Prompt: verify_research_v1
- Schema: youask_math_solver_solve_research_detailed_v1.schema.json
- Request ID: chatcmpl-D5i12TOItrbttnL5TPVcID5aBfOAU
- Latency: 25151ms
- Tokens: 2095 in / 643 out
- Success: True
- Final Answer: 

### Plot Trigger Call
- Developer Prompt: plot_trigger_v1
- Schema: youask_plot_trigger_v1.schema.json
- Request ID: None
- Latency: 0ms
- Tokens: 0 in / 0 out
- Success: False

### Summary
- Plot Generated: False
- Plot ID: None
- Errors: ['Unexpected answer: ', 'Trigger failed: No active prompt binding found for tier=RESEARCH mode=PLOT_TRIGGER.']

## Overall Summary
- All solves successful: False
- All plots generated: False
- Total errors: 5