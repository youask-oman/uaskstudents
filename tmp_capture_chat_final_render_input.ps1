$ErrorActionPreference = "Stop"
$sessionId = 63
$base = "http://localhost:9000/api/v1"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$rawPath = "reports/chat_final_live_session_${sessionId}_raw_${ts}.json"
$reviewPath = "reports/chat_final_live_session_${sessionId}_render_input_${ts}.json"
$resolvedPath = "reports/chat_final_live_session_${sessionId}_resolved_text_${ts}.txt"

$session = Invoke-RestMethod -Method Get -Uri "$base/sessions/$sessionId"
$session | ConvertTo-Json -Depth 100 | Set-Content -Path $rawPath -Encoding UTF8

$messages = @($session.messages)
$assistant = $null
for ($i = $messages.Count - 1; $i -ge 0; $i--) {
  if ([string]$messages[$i].role -eq "assistant") { $assistant = $messages[$i]; break }
}
if (-not $assistant) { throw "No assistant message found" }
$messageId = [string]$assistant.id

$playback = Invoke-RestMethod -Method Get -Uri "$base/chat_final/playback_state?message_id=$messageId"

$structured = $assistant.structured_data
$solutions = @($structured.solutions)
$q1 = $null
if ($solutions.Count -gt 0) { $q1 = $solutions[0] }

$steps = @()
if ($q1 -and $q1.steps) {
  $steps = @($q1.steps | ForEach-Object {
    [ordered]@{
      index = $_.index
      title = $_.title
      explanation = $_.explanation
      raw = $_.raw
      math_latex = $_.math_latex
    }
  })
}

$report = [ordered]@{
  captured_at_utc = (Get-Date).ToUniversalTime().ToString("o")
  source_endpoint = "GET $base/sessions/$sessionId"
  playback_endpoint = "GET $base/chat_final/playback_state?message_id=$messageId"
  render_source_in_frontend = "extractAssistantPlaybackSource -> resolvePlaybackFromMessage"
  assistant_message_id = $messageId
  assistant_content_len = ([string]$assistant.content).Length
  assistant_display_markdown_len = ([string]$assistant.display_markdown).Length
  assistant_rendered_content_len = ([string]$assistant.rendered_content).Length
  structured_keys = @($structured.PSObject.Properties.Name)
  structured_question_count = @($structured.questions).Count
  structured_solution_count = @($structured.solutions).Count
  q1_steps_exact_used_for_display = $steps
  q1_final_answer = if ($q1) { $q1.final_answer } else { $null }
  playback_state = $playback
  files = [ordered]@{
    raw_session_json = $rawPath
    review_json = $reviewPath
    resolved_text = $resolvedPath
  }
}

$report | ConvertTo-Json -Depth 100 | Set-Content -Path $reviewPath -Encoding UTF8
([string]$playback.full_text) | Set-Content -Path $resolvedPath -Encoding UTF8

Write-Output "RAW=$rawPath"
Write-Output "REVIEW=$reviewPath"
Write-Output "RESOLVED=$resolvedPath"
Write-Output "MESSAGE_ID=$messageId"
Write-Output "VISIBLE_LEN=$($playback.visible_len)"
Write-Output "IS_COMPLETE=$($playback.is_complete)"
Write-Output "FULL_TEXT_PREVIEW_START"
$preview = [string]$playback.full_text
if ($preview.Length -gt 700) { $preview = $preview.Substring(0,700) }
Write-Output $preview
Write-Output "FULL_TEXT_PREVIEW_END"
