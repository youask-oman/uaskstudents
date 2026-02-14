# Full Tier OpenAI Execution Report

Generated at: 2026-02-14T06:31:40.939139Z

## FREE
- request_id: `tier-free-1771050320-ff28f00e-c7d4-4343-90d5-fbaa7f0a595c`
- attempt_id: `69c8117b-cc12-44b5-b05b-1d6aebdce319`
- OpenAI visits in this tier window: **3**
- Main prompt IDs (from attempt meta): system=`global_system_prompt_v2_compact.txt`, developer=`solve_orchestrator_developer_v2_compact.txt`, schema=`solve_superset_v2.schema.json`
- Per-tier visit evidence JSON: `reports\tier_live_runs\free_tier-free-1771050320-ff28f00e-c7d4-4343-90d5-fbaa7f0a595c_openai_visits.json`

### Visit 1: solve_main
- worker.log line: `70722`
- OpenAI request_id: `req_17c70e9c9fd14d1c93c897e6cb54bca1`
- HTTP: `2026-02-13 22:25:32,424 [DEBUG] openai._base_client: HTTP Response: POST https://api.openai.com/v1/responses "200 OK" Headers({'date': 'Sat, 14 Feb 2026 06:25:32 GMT', 'content-type': 'application/json', 'transfer-encoding': 'chunked', 'connection': 'keep-alive', 'server': 'cloudflare', 'openai-version': '2020-10-01', 'openai-organization': 'user-yacbgrjb6nsf3pyihwxlrnej', 'openai-project': 'proj_f0eOR3UtUwq4hiQhpePdIrjx', 'x-request-id': 'req_17c70e9c9fd14d1c93c897e6cb54bca1', 'openai-processing-ms': '11282', 'cf-cache-status': 'DYNAMIC', 'x-content-type-options': 'nosniff', 'strict-transport-security': 'max-age=31536000; includeSubDomains; preload', 'content-encoding': 'gzip', 'cf-ray': '9cda7cdacdaebbe0-YVR', 'alt-svc': 'h3=":443"; ma=86400'})`
- Full input payload (exact logged request options line): `reports\tier_live_runs\report_assets\free_tier-free-1771050320-ff28f00e-c7d4-4343-90d5-fbaa7f0a595c_visit1_request_options.logline.txt`
- Full OpenAI output raw_text: `reports\tier_live_runs\report_assets\free_tier-free-1771050320-ff28f00e-c7d4-4343-90d5-fbaa7f0a595c_visit1_openai_output_raw_text.txt`
- Parsed output JSON (post-parse object stored): `reports\tier_live_runs\report_assets\free_tier-free-1771050320-ff28f00e-c7d4-4343-90d5-fbaa7f0a595c_visit1_openai_output_parsed_json.json`
- Usage: `{"input_tokens": 4041, "output_tokens": 1300, "total_tokens": 5341}`

### Visit 2: solve_json_repair
- worker.log line: `70746`
- OpenAI request_id: `req_85371ff4170e4986bf192c44f1995ff8`
- HTTP: `2026-02-13 22:25:43,115 [DEBUG] openai._base_client: HTTP Response: POST https://api.openai.com/v1/responses "200 OK" Headers({'date': 'Sat, 14 Feb 2026 06:25:43 GMT', 'content-type': 'application/json', 'transfer-encoding': 'chunked', 'connection': 'keep-alive', 'server': 'cloudflare', 'openai-version': '2020-10-01', 'openai-organization': 'user-yacbgrjb6nsf3pyihwxlrnej', 'openai-project': 'proj_f0eOR3UtUwq4hiQhpePdIrjx', 'x-request-id': 'req_85371ff4170e4986bf192c44f1995ff8', 'openai-processing-ms': '10288', 'cf-cache-status': 'DYNAMIC', 'x-content-type-options': 'nosniff', 'strict-transport-security': 'max-age=31536000; includeSubDomains; preload', 'content-encoding': 'gzip', 'cf-ray': '9cda7d22c8e0bbe0-YVR', 'alt-svc': 'h3=":443"; ma=86400'})`
- Full input payload (exact logged request options line): `reports\tier_live_runs\report_assets\free_tier-free-1771050320-ff28f00e-c7d4-4343-90d5-fbaa7f0a595c_visit2_request_options.logline.txt`
- Full OpenAI output raw_text: `reports\tier_live_runs\report_assets\free_tier-free-1771050320-ff28f00e-c7d4-4343-90d5-fbaa7f0a595c_visit2_openai_output_raw_text.txt`
- Parsed output JSON (post-parse object stored): `reports\tier_live_runs\report_assets\free_tier-free-1771050320-ff28f00e-c7d4-4343-90d5-fbaa7f0a595c_visit2_openai_output_parsed_json.json`
- Usage: `{"input": 4041, "output": 1300, "total": 5341}`

### Visit 3: plot_spec
- worker.log line: `70767`
- OpenAI request_id: `req_f39a650aec184ccabd6f1bcf67e31afa`
- HTTP: `2026-02-13 22:25:43,500 [DEBUG] openai._base_client: HTTP Response: POST https://api.openai.com/v1/chat/completions "400 Bad Request" Headers({'date': 'Sat, 14 Feb 2026 06:25:43 GMT', 'content-type': 'application/json', 'content-length': '245', 'connection': 'keep-alive', 'access-control-expose-headers': 'X-Request-ID', 'openai-organization': 'user-yacbgrjb6nsf3pyihwxlrnej', 'openai-processing-ms': '14', 'openai-project': 'proj_f0eOR3UtUwq4hiQhpePdIrjx', 'openai-version': '2020-10-01', 'server': 'cloudflare', 'x-ratelimit-limit-requests': '500', 'x-ratelimit-limit-tokens': '500000', 'x-ratelimit-remaining-requests': '499', 'x-ratelimit-remaining-tokens': '498989', 'x-ratelimit-reset-requests': '120ms', 'x-ratelimit-reset-tokens': '121ms', 'x-request-id': 'req_f39a650aec184ccabd6f1bcf67e31afa', 'x-openai-proxy-wasm': 'v0.1', 'cf-cache-status': 'DYNAMIC', 'set-cookie': '__cf_bm=obHUUdNi8LGtZcsxRogbaQEMpdm3qcRlHGMb5Xve9ow-1771050343.5337017-1.0.1.1-TuAgxZDE7RJ9rlv_B5qgUmzUDGZvLO4Zf2iOrRj7kC7bcYR6mbYRSF76xP_yjSYfa4lioog0aUfVhsS.Jeo0fVDk28eDbNqx2HQ69cBLHX32X4T9kjKEtex6DOmA2Ttm; HttpOnly; Secure; Path=/; Domain=api.openai.com; Expires=Sat, 14 Feb 2026 06:55:43 GMT', 'strict-transport-security': 'max-age=31536000; includeSubDomains; preload', 'x-content-type-options': 'nosniff', 'cf-ray': '9cda7d6718468d3e-YVR', 'alt-svc': 'h3=":443"; ma=86400'})`
- Error: `openai.BadRequestError: Error code: 400 - {'error': {'message': "Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead.", 'type': 'invalid_request_error', 'param': 'max_tokens', 'code': 'unsupported_parameter'}}`
- Full input payload (exact logged request options line): `reports\tier_live_runs\report_assets\free_tier-free-1771050320-ff28f00e-c7d4-4343-90d5-fbaa7f0a595c_visit3_request_options.logline.txt`

## SHORT
- request_id: `tier-short-1771050343-2e398d94-9f68-455b-891c-64923bc27a02`
- attempt_id: `0adcc830-7a14-425f-ae32-0fc8506bf300`
- OpenAI visits in this tier window: **4**
- Main prompt IDs (from attempt meta): system=`global_system_prompt_v2_compact.txt`, developer=`solve_final_answer_v1`, schema=`solve_final_answer_v1.schema.json`
- Per-tier visit evidence JSON: `reports\tier_live_runs\short_tier-short-1771050343-2e398d94-9f68-455b-891c-64923bc27a02_openai_visits.json`

### Visit 1: solve_main
- worker.log line: `70826`
- OpenAI request_id: `req_8ba40c5b2ed4495ba6cc20821f914e14`
- HTTP: `2026-02-13 22:25:50,731 [DEBUG] openai._base_client: HTTP Response: POST https://api.openai.com/v1/responses "200 OK" Headers({'date': 'Sat, 14 Feb 2026 06:25:50 GMT', 'content-type': 'application/json', 'transfer-encoding': 'chunked', 'connection': 'keep-alive', 'server': 'cloudflare', 'openai-version': '2020-10-01', 'openai-organization': 'user-yacbgrjb6nsf3pyihwxlrnej', 'openai-project': 'proj_f0eOR3UtUwq4hiQhpePdIrjx', 'x-request-id': 'req_8ba40c5b2ed4495ba6cc20821f914e14', 'openai-processing-ms': '6804', 'cf-cache-status': 'DYNAMIC', 'x-content-type-options': 'nosniff', 'strict-transport-security': 'max-age=31536000; includeSubDomains; preload', 'content-encoding': 'gzip', 'cf-ray': '9cda7d69f8a2bbe0-YVR', 'alt-svc': 'h3=":443"; ma=86400'})`
- Full input payload (exact logged request options line): `reports\tier_live_runs\report_assets\short_tier-short-1771050343-2e398d94-9f68-455b-891c-64923bc27a02_visit1_request_options.logline.txt`
- Full OpenAI output raw_text: `reports\tier_live_runs\report_assets\short_tier-short-1771050343-2e398d94-9f68-455b-891c-64923bc27a02_visit1_openai_output_raw_text.txt`
- Parsed output JSON (post-parse object stored): `reports\tier_live_runs\report_assets\short_tier-short-1771050343-2e398d94-9f68-455b-891c-64923bc27a02_visit1_openai_output_parsed_json.json`
- Usage: `{"input_tokens": 2221, "output_tokens": 900, "total_tokens": 3121}`

### Visit 2: solve_json_repair
- worker.log line: `70844`
- OpenAI request_id: `req_bc5b7e7d64ed4115922c5652596d840c`
- HTTP: `2026-02-13 22:25:57,607 [DEBUG] openai._base_client: HTTP Response: POST https://api.openai.com/v1/responses "200 OK" Headers({'date': 'Sat, 14 Feb 2026 06:25:57 GMT', 'content-type': 'application/json', 'transfer-encoding': 'chunked', 'connection': 'keep-alive', 'server': 'cloudflare', 'x-ratelimit-limit-requests': '500', 'x-ratelimit-limit-tokens': '500000', 'x-ratelimit-remaining-requests': '499', 'x-ratelimit-remaining-tokens': '499327', 'x-ratelimit-reset-requests': '120ms', 'x-ratelimit-reset-tokens': '80ms', 'openai-version': '2020-10-01', 'openai-organization': 'user-yacbgrjb6nsf3pyihwxlrnej', 'openai-project': 'proj_f0eOR3UtUwq4hiQhpePdIrjx', 'x-request-id': 'req_bc5b7e7d64ed4115922c5652596d840c', 'openai-processing-ms': '6712', 'cf-cache-status': 'DYNAMIC', 'x-content-type-options': 'nosniff', 'strict-transport-security': 'max-age=31536000; includeSubDomains; preload', 'content-encoding': 'gzip', 'cf-ray': '9cda7d953909bbe0-YVR', 'alt-svc': 'h3=":443"; ma=86400'})`
- Full input payload (exact logged request options line): `reports\tier_live_runs\report_assets\short_tier-short-1771050343-2e398d94-9f68-455b-891c-64923bc27a02_visit2_request_options.logline.txt`
- Full OpenAI output raw_text: `reports\tier_live_runs\report_assets\short_tier-short-1771050343-2e398d94-9f68-455b-891c-64923bc27a02_visit2_openai_output_raw_text.txt`
- Parsed output JSON (post-parse object stored): `reports\tier_live_runs\report_assets\short_tier-short-1771050343-2e398d94-9f68-455b-891c-64923bc27a02_visit2_openai_output_parsed_json.json`
- Usage: `{"input": 2221, "output": 900, "total": 3121}`

### Visit 3: plot_trigger
- worker.log line: `70863`
- OpenAI request_id: `req_347a1a8b597c417cb6408a427c7f7952`
- HTTP: `2026-02-13 22:25:58,055 [DEBUG] openai._base_client: HTTP Response: POST https://api.openai.com/v1/chat/completions "400 Bad Request" Headers({'date': 'Sat, 14 Feb 2026 06:25:58 GMT', 'content-type': 'application/json', 'content-length': '245', 'connection': 'keep-alive', 'access-control-expose-headers': 'X-Request-ID', 'openai-organization': 'user-yacbgrjb6nsf3pyihwxlrnej', 'openai-processing-ms': '9', 'openai-project': 'proj_f0eOR3UtUwq4hiQhpePdIrjx', 'openai-version': '2020-10-01', 'server': 'cloudflare', 'x-ratelimit-limit-requests': '500', 'x-ratelimit-limit-tokens': '500000', 'x-ratelimit-remaining-requests': '499', 'x-ratelimit-remaining-tokens': '499201', 'x-ratelimit-reset-requests': '120ms', 'x-ratelimit-reset-tokens': '95ms', 'x-request-id': 'req_347a1a8b597c417cb6408a427c7f7952', 'x-openai-proxy-wasm': 'v0.1', 'cf-cache-status': 'DYNAMIC', 'set-cookie': '__cf_bm=567htl6ZXohglxFD82.lpxi56elwf38ZpMoOlpuCEkE-1771050358.0931978-1.0.1.1-GPttNgAqdC.3OoHZ9rDCmLoOoxrftxnnpJT90s2kM3dfkbwJNFNaOwmk2e8Zo6T.zl0wu9o7dbY1KFJKIhiSNgBPs4pttrExvtKJpPBFHmjktawJUvSFx59KEkC25Qzt; HttpOnly; Secure; Path=/; Domain=api.openai.com; Expires=Sat, 14 Feb 2026 06:55:58 GMT', 'strict-transport-security': 'max-age=31536000; includeSubDomains; preload', 'x-content-type-options': 'nosniff', 'cf-ray': '9cda7dc21a310b4b-YVR', 'alt-svc': 'h3=":443"; ma=86400'})`
- Error: `2026-02-13 22:25:58,056 [ERROR] app.services.plot_pipeline_service: [PLOT_TRIGGER] OpenAI error: Error code: 400 - {'error': {'message': "Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead.", 'type': 'invalid_request_error', 'param': 'max_tokens', 'code': 'unsupported_parameter'}}`
- Full input payload (exact logged request options line): `reports\tier_live_runs\report_assets\short_tier-short-1771050343-2e398d94-9f68-455b-891c-64923bc27a02_visit3_request_options.logline.txt`

### Visit 4: plot_spec
- worker.log line: `70896`
- OpenAI request_id: `req_b9a50d604a1a45acb44d80579222feab`
- HTTP: `2026-02-13 22:25:58,670 [DEBUG] openai._base_client: HTTP Response: POST https://api.openai.com/v1/chat/completions "400 Bad Request" Headers({'date': 'Sat, 14 Feb 2026 06:25:58 GMT', 'content-type': 'application/json', 'content-length': '245', 'connection': 'keep-alive', 'access-control-expose-headers': 'X-Request-ID', 'openai-organization': 'user-yacbgrjb6nsf3pyihwxlrnej', 'openai-processing-ms': '9', 'openai-project': 'proj_f0eOR3UtUwq4hiQhpePdIrjx', 'openai-version': '2020-10-01', 'server': 'cloudflare', 'x-ratelimit-limit-requests': '500', 'x-ratelimit-limit-tokens': '500000', 'x-ratelimit-remaining-requests': '499', 'x-ratelimit-remaining-tokens': '499021', 'x-ratelimit-reset-requests': '120ms', 'x-ratelimit-reset-tokens': '117ms', 'x-request-id': 'req_b9a50d604a1a45acb44d80579222feab', 'x-openai-proxy-wasm': 'v0.1', 'cf-cache-status': 'DYNAMIC', 'x-content-type-options': 'nosniff', 'strict-transport-security': 'max-age=31536000; includeSubDomains; preload', 'cf-ray': '9cda7dc2ebb70b4b-YVR', 'alt-svc': 'h3=":443"; ma=86400'})`
- Error: `openai.BadRequestError: Error code: 400 - {'error': {'message': "Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead.", 'type': 'invalid_request_error', 'param': 'max_tokens', 'code': 'unsupported_parameter'}}`
- Full input payload (exact logged request options line): `reports\tier_live_runs\report_assets\short_tier-short-1771050343-2e398d94-9f68-455b-891c-64923bc27a02_visit4_request_options.logline.txt`

## STANDARD
- request_id: `tier-standard-1771050358-ae283167-566c-4973-8d44-5cb5665252cd`
- attempt_id: `ab9754f1-5df8-4355-a5d0-aca7f460fe61`
- OpenAI visits in this tier window: **3**
- Main prompt IDs (from attempt meta): system=`global_system_prompt_v2_compact.txt`, developer=`solve_standard_v1`, schema=`solve_standard_detailed_v1.schema.json`
- Per-tier visit evidence JSON: `reports\tier_live_runs\standard_tier-standard-1771050358-ae283167-566c-4973-8d44-5cb5665252cd_openai_visits.json`

### Visit 1: solve_main
- worker.log line: `70956`
- OpenAI request_id: `req_8ba9d05e14024fd3b2bbefb258c9517e`
- HTTP: `2026-02-13 22:26:19,364 [DEBUG] openai._base_client: HTTP Response: POST https://api.openai.com/v1/responses "200 OK" Headers({'date': 'Sat, 14 Feb 2026 06:26:19 GMT', 'content-type': 'application/json', 'transfer-encoding': 'chunked', 'connection': 'keep-alive', 'server': 'cloudflare', 'x-ratelimit-limit-requests': '500', 'x-ratelimit-limit-tokens': '500000', 'x-ratelimit-remaining-requests': '499', 'x-ratelimit-remaining-tokens': '497542', 'x-ratelimit-reset-requests': '120ms', 'x-ratelimit-reset-tokens': '294ms', 'openai-version': '2020-10-01', 'openai-organization': 'user-yacbgrjb6nsf3pyihwxlrnej', 'openai-project': 'proj_f0eOR3UtUwq4hiQhpePdIrjx', 'x-request-id': 'req_8ba9d05e14024fd3b2bbefb258c9517e', 'openai-processing-ms': '20322', 'cf-cache-status': 'DYNAMIC', 'x-content-type-options': 'nosniff', 'strict-transport-security': 'max-age=31536000; includeSubDomains; preload', 'content-encoding': 'gzip', 'cf-ray': '9cda7dc87e01bbe0-YVR', 'alt-svc': 'h3=":443"; ma=86400'})`
- Full input payload (exact logged request options line): `reports\tier_live_runs\report_assets\standard_tier-standard-1771050358-ae283167-566c-4973-8d44-5cb5665252cd_visit1_request_options.logline.txt`
- Full OpenAI output raw_text: `reports\tier_live_runs\report_assets\standard_tier-standard-1771050358-ae283167-566c-4973-8d44-5cb5665252cd_visit1_openai_output_raw_text.txt`
- Parsed output JSON (post-parse object stored): `reports\tier_live_runs\report_assets\standard_tier-standard-1771050358-ae283167-566c-4973-8d44-5cb5665252cd_visit1_openai_output_parsed_json.json`
- Usage: `{"input_tokens": 4504, "output_tokens": 2675, "total_tokens": 7179}`

### Visit 2: solve_json_repair
- worker.log line: `70976`
- OpenAI request_id: `req_cc1f6f221a41435889e58a60cca4acea`
- HTTP: `2026-02-13 22:26:39,421 [DEBUG] openai._base_client: HTTP Response: POST https://api.openai.com/v1/responses "200 OK" Headers({'date': 'Sat, 14 Feb 2026 06:26:39 GMT', 'content-type': 'application/json', 'transfer-encoding': 'chunked', 'connection': 'keep-alive', 'server': 'cloudflare', 'x-ratelimit-limit-requests': '500', 'x-ratelimit-limit-tokens': '500000', 'x-ratelimit-remaining-requests': '499', 'x-ratelimit-remaining-tokens': '497649', 'x-ratelimit-reset-requests': '120ms', 'x-ratelimit-reset-tokens': '282ms', 'openai-version': '2020-10-01', 'openai-organization': 'user-yacbgrjb6nsf3pyihwxlrnej', 'openai-project': 'proj_f0eOR3UtUwq4hiQhpePdIrjx', 'x-request-id': 'req_cc1f6f221a41435889e58a60cca4acea', 'openai-processing-ms': '19837', 'cf-cache-status': 'DYNAMIC', 'x-content-type-options': 'nosniff', 'strict-transport-security': 'max-age=31536000; includeSubDomains; preload', 'content-encoding': 'gzip', 'cf-ray': '9cda7e487f1cbbe0-YVR', 'alt-svc': 'h3=":443"; ma=86400'})`
- Full input payload (exact logged request options line): `reports\tier_live_runs\report_assets\standard_tier-standard-1771050358-ae283167-566c-4973-8d44-5cb5665252cd_visit2_request_options.logline.txt`
- Full OpenAI output raw_text: `reports\tier_live_runs\report_assets\standard_tier-standard-1771050358-ae283167-566c-4973-8d44-5cb5665252cd_visit2_openai_output_raw_text.txt`
- Parsed output JSON (post-parse object stored): `reports\tier_live_runs\report_assets\standard_tier-standard-1771050358-ae283167-566c-4973-8d44-5cb5665252cd_visit2_openai_output_parsed_json.json`
- Usage: `{"input": 4504, "output": 2675, "total": 7179}`

### Visit 3: plot_spec
- worker.log line: `70999`
- OpenAI request_id: `req_30f0cf0e5fc44915ac08b515371f888c`
- HTTP: `2026-02-13 22:26:40,689 [DEBUG] openai._base_client: HTTP Response: POST https://api.openai.com/v1/chat/completions "400 Bad Request" Headers({'date': 'Sat, 14 Feb 2026 06:26:40 GMT', 'content-type': 'application/json', 'content-length': '245', 'connection': 'keep-alive', 'access-control-expose-headers': 'X-Request-ID', 'openai-organization': 'user-yacbgrjb6nsf3pyihwxlrnej', 'openai-processing-ms': '8', 'openai-project': 'proj_f0eOR3UtUwq4hiQhpePdIrjx', 'openai-version': '2020-10-01', 'server': 'cloudflare', 'x-ratelimit-limit-requests': '500', 'x-ratelimit-limit-tokens': '500000', 'x-ratelimit-remaining-requests': '499', 'x-ratelimit-remaining-tokens': '499020', 'x-ratelimit-reset-requests': '120ms', 'x-ratelimit-reset-tokens': '117ms', 'x-request-id': 'req_30f0cf0e5fc44915ac08b515371f888c', 'x-openai-proxy-wasm': 'v0.1', 'cf-cache-status': 'DYNAMIC', 'set-cookie': '__cf_bm=f_N8gpqNpKWgfT5YYszb1EdGSQIg5BErk3i_7O8BjBw-1771050399.8547583-1.0.1.1-JV9cVHQ4h0J0rh6O66hQ0TTB8AcX2KTLklGwIf1VojyTG7yOk..JQ2WEpOilYs.F2gPHMfwEgjjnT2mZDjyANMQUXyPslw1jYb38iq2AgcxMNEyCn4hxb38ueBoDEo7T; HttpOnly; Secure; Path=/; Domain=api.openai.com; Expires=Sat, 14 Feb 2026 06:56:40 GMT', 'strict-transport-security': 'max-age=31536000; includeSubDomains; preload', 'x-content-type-options': 'nosniff', 'cf-ray': '9cda7ec71dadd9c8-YVR', 'alt-svc': 'h3=":443"; ma=86400'})`
- Error: `openai.BadRequestError: Error code: 400 - {'error': {'message': "Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead.", 'type': 'invalid_request_error', 'param': 'max_tokens', 'code': 'unsupported_parameter'}}`
- Full input payload (exact logged request options line): `reports\tier_live_runs\report_assets\standard_tier-standard-1771050358-ae283167-566c-4973-8d44-5cb5665252cd_visit3_request_options.logline.txt`

## RESEARCH
- request_id: `tier-research-1771050400-405f8d88-f464-45ed-b4e0-4ab434a2f31f`
- attempt_id: `eb9ce1d4-7fe7-40bc-97c7-fe06eb21194f`
- OpenAI visits in this tier window: **3**
- Main prompt IDs (from attempt meta): system=`global_system_prompt_v2_compact.txt`, developer=`solve_research_v1`, schema=`solve_research_detailed_v1.schema.json`
- Per-tier visit evidence JSON: `reports\tier_live_runs\research_tier-research-1771050400-405f8d88-f464-45ed-b4e0-4ab434a2f31f_openai_visits.json`

### Visit 1: solve_main
- worker.log line: `71060`
- OpenAI request_id: `req_772d2302b2b142c9a7438b7e70364b66`
- HTTP: `2026-02-13 22:27:07,856 [DEBUG] openai._base_client: HTTP Response: POST https://api.openai.com/v1/responses "200 OK" Headers({'date': 'Sat, 14 Feb 2026 06:27:07 GMT', 'content-type': 'application/json', 'transfer-encoding': 'chunked', 'connection': 'keep-alive', 'server': 'cloudflare', 'x-ratelimit-limit-requests': '500', 'x-ratelimit-limit-tokens': '500000', 'x-ratelimit-remaining-requests': '499', 'x-ratelimit-remaining-tokens': '496729', 'x-ratelimit-reset-requests': '120ms', 'x-ratelimit-reset-tokens': '392ms', 'openai-version': '2020-10-01', 'openai-organization': 'user-yacbgrjb6nsf3pyihwxlrnej', 'openai-project': 'proj_f0eOR3UtUwq4hiQhpePdIrjx', 'x-request-id': 'req_772d2302b2b142c9a7438b7e70364b66', 'openai-processing-ms': '26704', 'cf-cache-status': 'DYNAMIC', 'x-content-type-options': 'nosniff', 'strict-transport-security': 'max-age=31536000; includeSubDomains; preload', 'content-encoding': 'gzip', 'cf-ray': '9cda7ecf08c4bbe0-YVR', 'alt-svc': 'h3=":443"; ma=86400'})`
- Full input payload (exact logged request options line): `reports\tier_live_runs\report_assets\research_tier-research-1771050400-405f8d88-f464-45ed-b4e0-4ab434a2f31f_visit1_request_options.logline.txt`
- Full OpenAI output raw_text: `reports\tier_live_runs\report_assets\research_tier-research-1771050400-405f8d88-f464-45ed-b4e0-4ab434a2f31f_visit1_openai_output_raw_text.txt`
- Parsed output JSON (post-parse object stored): `reports\tier_live_runs\report_assets\research_tier-research-1771050400-405f8d88-f464-45ed-b4e0-4ab434a2f31f_visit1_openai_output_parsed_json.json`
- Usage: `{"input_tokens": 5057, "output_tokens": 3488, "total_tokens": 8545}`

### Visit 2: solve_json_repair
- worker.log line: `71080`
- OpenAI request_id: `req_151c1e0c1b5242a2a484254ea7207f6f`
- HTTP: `2026-02-13 22:27:35,885 [DEBUG] openai._base_client: HTTP Response: POST https://api.openai.com/v1/responses "200 OK" Headers({'date': 'Sat, 14 Feb 2026 06:27:35 GMT', 'content-type': 'application/json', 'transfer-encoding': 'chunked', 'connection': 'keep-alive', 'server': 'cloudflare', 'x-ratelimit-limit-requests': '500', 'x-ratelimit-limit-tokens': '500000', 'x-ratelimit-remaining-requests': '499', 'x-ratelimit-remaining-tokens': '496753', 'x-ratelimit-reset-requests': '120ms', 'x-ratelimit-reset-tokens': '389ms', 'openai-version': '2020-10-01', 'openai-organization': 'user-yacbgrjb6nsf3pyihwxlrnej', 'openai-project': 'proj_f0eOR3UtUwq4hiQhpePdIrjx', 'x-request-id': 'req_151c1e0c1b5242a2a484254ea7207f6f', 'openai-processing-ms': '27751', 'cf-cache-status': 'DYNAMIC', 'x-content-type-options': 'nosniff', 'strict-transport-security': 'max-age=31536000; includeSubDomains; preload', 'content-encoding': 'gzip', 'cf-ray': '9cda7f779a07bbe0-YVR', 'alt-svc': 'h3=":443"; ma=86400'})`
- Full input payload (exact logged request options line): `reports\tier_live_runs\report_assets\research_tier-research-1771050400-405f8d88-f464-45ed-b4e0-4ab434a2f31f_visit2_request_options.logline.txt`
- Full OpenAI output raw_text: `reports\tier_live_runs\report_assets\research_tier-research-1771050400-405f8d88-f464-45ed-b4e0-4ab434a2f31f_visit2_openai_output_raw_text.txt`
- Parsed output JSON (post-parse object stored): `reports\tier_live_runs\report_assets\research_tier-research-1771050400-405f8d88-f464-45ed-b4e0-4ab434a2f31f_visit2_openai_output_parsed_json.json`
- Usage: `{"input": 5057, "output": 3488, "total": 8545}`

### Visit 3: plot_spec
- worker.log line: `71105`
- OpenAI request_id: `req_81408c97be4944fcaebc181dcd30afea`
- HTTP: `2026-02-13 22:27:37,171 [DEBUG] openai._base_client: HTTP Response: POST https://api.openai.com/v1/chat/completions "400 Bad Request" Headers({'date': 'Sat, 14 Feb 2026 06:27:37 GMT', 'content-type': 'application/json', 'content-length': '245', 'connection': 'keep-alive', 'access-control-expose-headers': 'X-Request-ID', 'openai-organization': 'user-yacbgrjb6nsf3pyihwxlrnej', 'openai-processing-ms': '8', 'openai-project': 'proj_f0eOR3UtUwq4hiQhpePdIrjx', 'openai-version': '2020-10-01', 'server': 'cloudflare', 'x-ratelimit-limit-requests': '500', 'x-ratelimit-limit-tokens': '500000', 'x-ratelimit-remaining-requests': '499', 'x-ratelimit-remaining-tokens': '499020', 'x-ratelimit-reset-requests': '120ms', 'x-ratelimit-reset-tokens': '117ms', 'x-request-id': 'req_81408c97be4944fcaebc181dcd30afea', 'x-openai-proxy-wasm': 'v0.1', 'cf-cache-status': 'DYNAMIC', 'set-cookie': '__cf_bm=I5XKPWYscP8jGKBk.z_iYLYd1WTbcx9YLXTowEJymk8-1771050456.3321636-1.0.1.1-1A5w85oIl5u_Tj6Ik__yF7KXQhXli5Qc1BcdOYxMJ.Co.1UtcZ7Ge.1G9eNK6tTfxL0RGjJY4cF6prvo6gPt3mNvrBYkXJnT4QbLnOrZ2RjgqN4tEuKacHr3qoAUfH8R; HttpOnly; Secure; Path=/; Domain=api.openai.com; Expires=Sat, 14 Feb 2026 06:57:37 GMT', 'strict-transport-security': 'max-age=31536000; includeSubDomains; preload', 'x-content-type-options': 'nosniff', 'cf-ray': '9cda80281e4c5768-YVR', 'alt-svc': 'h3=":443"; ma=86400'})`
- Error: `openai.BadRequestError: Error code: 400 - {'error': {'message': "Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead.", 'type': 'invalid_request_error', 'param': 'max_tokens', 'code': 'unsupported_parameter'}}`
- Full input payload (exact logged request options line): `reports\tier_live_runs\report_assets\research_tier-research-1771050400-405f8d88-f464-45ed-b4e0-4ab434a2f31f_visit3_request_options.logline.txt`

## Prompt And Schema Assets
- Prompt `global_system_prompt_v2_compact.txt` full content: `reports/tier_live_runs/report_assets/prompt__global_system_prompt_v2_compact.txt.txt`
- Prompt `plot_trigger_v1` full content: `reports/tier_live_runs/report_assets/prompt__plot_trigger_v1.txt`
- Prompt `solve_final_answer_v1` full content: `reports/tier_live_runs/report_assets/prompt__solve_final_answer_v1.txt`
- Prompt `solve_orchestrator_developer_v2_compact.txt` full content: `reports/tier_live_runs/report_assets/prompt__solve_orchestrator_developer_v2_compact.txt.txt`
- Prompt `solve_plot_spec_v2_compact.txt` full content: `reports/tier_live_runs/report_assets/prompt__solve_plot_spec_v2_compact.txt.txt`
- Prompt `solve_research_v1` full content: `reports/tier_live_runs/report_assets/prompt__solve_research_v1.txt`
- Prompt `solve_standard_v1` full content: `reports/tier_live_runs/report_assets/prompt__solve_standard_v1.txt`
- Schema `plot_trigger_v1.schema.json` full content: `reports/tier_live_runs/report_assets/schema__plot_trigger_v1.schema.json.json`
- Schema `solve_final_answer_v1.schema.json` full content: `reports/tier_live_runs/report_assets/schema__solve_final_answer_v1.schema.json.json`
- Schema `solve_research_detailed_v1.schema.json` full content: `reports/tier_live_runs/report_assets/schema__solve_research_detailed_v1.schema.json.json`
- Schema `solve_standard_detailed_v1.schema.json` full content: `reports/tier_live_runs/report_assets/schema__solve_standard_detailed_v1.schema.json.json`
- Schema `solve_superset_v2.schema.json` full content: `reports/tier_live_runs/report_assets/schema__solve_superset_v2.schema.json.json`

## Raw Run Artifacts
- SSE events: `reports/tier_live_runs/free_tier-free-1771050320-ff28f00e-c7d4-4343-90d5-fbaa7f0a595c_sse.json`
- Raw LLM output: `backend/logs/llm_raw_tier-free-1771050320-ff28f00e-c7d4-4343-90d5-fbaa7f0a595c.txt`
- Full LLM parsed log: `backend/logs/llm_full_tier-free-1771050320-ff28f00e-c7d4-4343-90d5-fbaa7f0a595c.log`
- SSE events: `reports/tier_live_runs/short_tier-short-1771050343-2e398d94-9f68-455b-891c-64923bc27a02_sse.json`
- Raw LLM output: `backend/logs/llm_raw_tier-short-1771050343-2e398d94-9f68-455b-891c-64923bc27a02.txt`
- Full LLM parsed log: `backend/logs/llm_full_tier-short-1771050343-2e398d94-9f68-455b-891c-64923bc27a02.log`
- SSE events: `reports/tier_live_runs/standard_tier-standard-1771050358-ae283167-566c-4973-8d44-5cb5665252cd_sse.json`
- Raw LLM output: `backend/logs/llm_raw_tier-standard-1771050358-ae283167-566c-4973-8d44-5cb5665252cd.txt`
- Full LLM parsed log: `backend/logs/llm_full_tier-standard-1771050358-ae283167-566c-4973-8d44-5cb5665252cd.log`
- SSE events: `reports/tier_live_runs/research_tier-research-1771050400-405f8d88-f464-45ed-b4e0-4ab434a2f31f_sse.json`
- Raw LLM output: `backend/logs/llm_raw_tier-research-1771050400-405f8d88-f464-45ed-b4e0-4ab434a2f31f.txt`
- Full LLM parsed log: `backend/logs/llm_full_tier-research-1771050400-405f8d88-f464-45ed-b4e0-4ab434a2f31f.log`