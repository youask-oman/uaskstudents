"""
OpenAI Debug Harness - Production-grade CLI tool for debugging OpenAI API calls.

This tool captures FULL request payloads and FULL responses from OpenAI,
with robust error handling, telemetry, and secret redaction.

Usage:
    python -m app.tools.openai_debug_harness --mode solve --detail minimal --learning solve \
        --question "Solve for x: 3(x-2)=15" --user_id 2

    python -m app.tools.openai_debug_harness --mode extract --source image --file path/to/crop.png
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import traceback

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Look for .env in the project root (parent of backend)
    env_path = Path(__file__).parent.parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"[ENV] Loaded environment from {env_path}")
    else:
        # Try current working directory
        load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, rely on existing env

from sqlmodel import Session, select
from app.database import get_session
from app.models import User, SystemConfig
from app.services.token_policy import get_token_policy, TokenPolicy, serialize_token_policy
from app.llm_profiles.profile_resolver import ProfileResolver
from app.llm_profiles.profiles import PromptProfile, get_prompt_profile
from app.schemas.na_math_solver_v3 import get_json_schema_for_openai_v3
from app.utils.schema_deref import deref_json_schema
from app.utils.schema_cleaner import enforce_strict
from app.services.validation_v3 import validate_response
from app.services.context_normalizer import build_compact_user_message, normalize_trusted_context
from app.utils.token_limits import get_effective_max_tokens

from openai import AsyncOpenAI


# =============================================================================
# Configuration & Dataclasses
# =============================================================================

@dataclass
class HarnessConfig:
    """Configuration for debug harness run."""
    mode: str = "solve"  # solve | extract
    detail: str = "minimal"  # minimal | detailed
    learning: str = "solve"  # solve | study
    question: str = ""
    user_id: int = 1
    source: str = "image"  # image | pdf (for extract mode)
    file_path: str = ""
    outdir: str = "app/storage/debug/openai"
    redact_input: bool = True
    redact_ocr: bool = True
    print_full_response: bool = True
    print_full_request: bool = True
    trace: bool = True


@dataclass
class RequestBundle:
    """Sanitized request bundle for logging."""
    model: str = ""
    max_output_tokens: int = 0
    reasoning_effort: Optional[str] = None
    system_prompt_length: int = 0
    system_prompt_preview: str = ""  # First 500 chars
    user_message_length: int = 0
    user_message_content: str = ""  # Full content (or sanitized)
    schema_name: str = ""
    schema_object: Dict[str, Any] = field(default_factory=dict)
    tool_definitions: Optional[List[Dict]] = None
    # Full payload for file save (secrets redacted)
    full_payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""


@dataclass
class ResponseBundle:
    """Full response capture from OpenAI."""
    status: str = ""  # completed | incomplete | error
    finish_reason: Optional[str] = None
    incomplete_details: Optional[Dict] = None
    error: Optional[Dict] = None
    
    # Usage
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    
    # Content
    raw_content: str = ""  # FULL raw content string
    content_length: int = 0
    content_preview_head: str = ""  # First 500 chars
    content_preview_tail: str = ""  # Last 500 chars
    
    # Headers (sanitized)
    request_id: Optional[str] = None
    rate_limit_remaining: Optional[int] = None
    
    # Full raw response object (for file save)
    full_response_dict: Dict[str, Any] = field(default_factory=dict)
    
    latency_ms: int = 0
    timestamp: str = ""


@dataclass
class ParseReport:
    """Step-by-step parsing diagnostics."""
    extracted_content_length: int = 0
    content_head_500: str = ""
    content_tail_500: str = ""
    
    json_loads_success: bool = False
    json_loads_error: Optional[str] = None
    json_error_position: Optional[int] = None
    json_error_context: Optional[str] = None  # +/- 120 chars around error
    
    schema_validation_success: bool = False
    schema_validation_errors: List[Dict] = field(default_factory=list)
    
    retry_performed: bool = False
    retry_reason: Optional[str] = None
    retry_success: bool = False
    
    final_status: str = ""  # success | parse_error | validation_error | fatal_error
    summary: str = ""


@dataclass
class DiagnosticResult:
    """Complete diagnostic result for a run."""
    run_id: str = ""
    config: Optional[HarnessConfig] = None
    request: Optional[RequestBundle] = None
    response: Optional[ResponseBundle] = None
    parse_report: Optional[ParseReport] = None
    telemetry: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Secret Redaction
# =============================================================================

SECRET_PATTERNS = [
    re.compile(r'(api[_-]?key)["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)', re.IGNORECASE),
    re.compile(r'(secret)["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)', re.IGNORECASE),
    re.compile(r'(password)["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)', re.IGNORECASE),
    re.compile(r'(authorization)["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)', re.IGNORECASE),
    re.compile(r'(bearer\s+)([^\s"\']+)', re.IGNORECASE),
    re.compile(r'sk-[a-zA-Z0-9-_]{20,}', re.IGNORECASE),  # OpenAI API key pattern
]


def redact_secrets(data: Any) -> Any:
    """Recursively redact secrets from data structure."""
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            key_lower = k.lower()
            # Only redact actual secret keys, not config like 'max_tokens'
            is_secret_key = any(s == key_lower or key_lower.endswith('_' + s) or key_lower.startswith(s + '_')
                               for s in ['api_key', 'apikey', 'secret', 'password', 'authorization', 'access_token', 'auth_token', 'bearer_token'])
            if is_secret_key:
                if isinstance(v, str) and len(v) > 8:
                    result[k] = v[:4] + "..." + v[-4:] + " [REDACTED]"
                else:
                    result[k] = "[REDACTED]"
            else:
                result[k] = redact_secrets(v)
        return result
    elif isinstance(data, list):
        return [redact_secrets(item) for item in data]
    elif isinstance(data, str):
        text = data
        # Handle sk- pattern separately (no capture group)
        text = re.sub(r'sk-[a-zA-Z0-9\-_]{20,}', '[REDACTED_KEY]', text, flags=re.IGNORECASE)
        # Handle other patterns with capture groups
        for pattern in SECRET_PATTERNS[:-1]:  # Exclude the last sk- pattern
            text = pattern.sub(lambda m: m.group(1) + ': [REDACTED]' if m.lastindex and m.lastindex >= 1 else '[REDACTED]', text)
        return text
    else:
        return data


def truncate_text(text: str, max_len: int = 500, show_both_ends: bool = True) -> str:
    """Truncate long text, optionally showing both ends."""
    if len(text) <= max_len:
        return text
    if show_both_ends:
        half = max_len // 2
        return text[:half] + f"\n\n... [{len(text) - max_len} chars truncated] ...\n\n" + text[-half:]
    return text[:max_len] + f"... [{len(text) - max_len} chars truncated]"


# =============================================================================
# Debug Harness Core
# =============================================================================

class DebugHarness:
    """Main debug harness for OpenAI API testing."""
    
    def __init__(self, config: HarnessConfig):
        self.config = config
        self.client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.model = os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini")
        self.run_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{config.mode}_{os.urandom(4).hex()}"
        self.output_dir = Path(config.outdir) / self.run_id
        
    def log(self, msg: str):
        """Print log message with timestamp."""
        if self.config.trace:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    
    async def run_solve(self) -> DiagnosticResult:
        """Run solve mode diagnostic."""
        result = DiagnosticResult(run_id=self.run_id, config=self.config)
        
        self.log(f"=== OPENAI DEBUG HARNESS: SOLVE MODE ===")
        self.log(f"Run ID: {self.run_id}")
        self.log(f"Question: {self.config.question}")
        self.log(f"Detail: {self.config.detail}, Learning: {self.config.learning}")
        
        # Get DB session
        session_gen = get_session()
        session: Session = next(session_gen)
        
        try:
            # Step 1: Resolve profile and token policy
            self.log("Step 1: Resolving profile and token policy...")
            
            user = session.get(User, self.config.user_id) if self.config.user_id else None
            
            profile = ProfileResolver.resolve_profile(
                session,
                user,
                requested_mode=self.config.detail,
                learning_mode=self.config.learning
            )
            
            token_policy = get_token_policy(session)
            
            self.log(f"  Profile: tier={profile.tier}, mode={profile.mode}")
            self.log(f"  Token Policy: minimal_solve={token_policy.text_output_minimal_solve}, detailed_solve={token_policy.text_output_detailed_solve}")
            
            # Step 2: Build request
            self.log("Step 2: Building request...")
            
            request_bundle, raw_params = self._build_solve_request(
                profile, token_policy, self.config.question
            )
            result.request = request_bundle
            
            self.log(f"  Model: {request_bundle.model}")
            self.log(f"  Max Output Tokens: {request_bundle.max_output_tokens}")
            self.log(f"  System Prompt Length: {request_bundle.system_prompt_length}")
            self.log(f"  User Message Length: {request_bundle.user_message_length}")
            self.log(f"  Schema: {request_bundle.schema_name}")
            
            # Step 3: Call OpenAI
            self.log("Step 3: Calling OpenAI...")
            start_time = time.perf_counter()
            
            response_bundle = await self._call_openai(raw_params)
            response_bundle.latency_ms = int((time.perf_counter() - start_time) * 1000)
            result.response = response_bundle
            
            self.log(f"  Status: {response_bundle.status}")
            self.log(f"  Finish Reason: {response_bundle.finish_reason}")
            self.log(f"  Latency: {response_bundle.latency_ms}ms")
            self.log(f"  Input Tokens: {response_bundle.input_tokens}")
            self.log(f"  Output Tokens: {response_bundle.output_tokens}")
            self.log(f"  Content Length: {response_bundle.content_length}")
            
            # Step 4: Parse and validate
            self.log("Step 4: Parsing and validating response...")
            
            parse_report = self._parse_and_validate(response_bundle.raw_content, profile)
            result.parse_report = parse_report
            
            self.log(f"  JSON Parse: {'SUCCESS' if parse_report.json_loads_success else 'FAILED'}")
            self.log(f"  Schema Valid: {'SUCCESS' if parse_report.schema_validation_success else 'FAILED'}")
            
            # Step 5: Retry if needed
            if not parse_report.json_loads_success or not parse_report.schema_validation_success:
                self.log("Step 5: Attempting retry...")
                
                parse_report.retry_performed = True
                if not parse_report.json_loads_success:
                    parse_report.retry_reason = f"JSON parse error: {parse_report.json_loads_error}"
                else:
                    parse_report.retry_reason = f"Schema validation errors: {len(parse_report.schema_validation_errors)}"
                
                # Increase token limit for retry
                retry_max_tokens = token_policy.text_output_retry_cap_detailed_solve
                raw_params_retry = raw_params.copy()
                raw_params_retry["max_output_tokens"] = retry_max_tokens
                
                self.log(f"  Retry with max_output_tokens={retry_max_tokens}")
                
                response_bundle_retry = await self._call_openai(raw_params_retry)
                parse_report_retry = self._parse_and_validate(response_bundle_retry.raw_content, profile)
                
                parse_report.retry_success = parse_report_retry.json_loads_success and parse_report_retry.schema_validation_success
                
                self.log(f"  Retry Result: {'SUCCESS' if parse_report.retry_success else 'FAILED'}")
            
            # Finalize
            if parse_report.json_loads_success and parse_report.schema_validation_success:
                parse_report.final_status = "success"
                parse_report.summary = "Request completed successfully. Response parsed and validated."
            elif parse_report.retry_success:
                parse_report.final_status = "success_after_retry"
                parse_report.summary = f"Request succeeded after retry. Initial failure: {parse_report.retry_reason}"
            elif not parse_report.json_loads_success:
                parse_report.final_status = "parse_error"
                parse_report.summary = f"JSON parsing failed: {parse_report.json_loads_error}"
            else:
                parse_report.final_status = "validation_error"
                parse_report.summary = f"Schema validation failed with {len(parse_report.schema_validation_errors)} errors"
            
            # Build telemetry
            result.telemetry = {
                "run_id": self.run_id,
                "mode": self.config.mode,
                "detail": self.config.detail,
                "learning": self.config.learning,
                "model": request_bundle.model,
                "max_output_tokens": request_bundle.max_output_tokens,
                "input_tokens": response_bundle.input_tokens,
                "output_tokens": response_bundle.output_tokens,
                "total_tokens": response_bundle.total_tokens,
                "cached_tokens": response_bundle.cached_tokens,
                "latency_ms": response_bundle.latency_ms,
                "content_length": response_bundle.content_length,
                "json_parse_success": parse_report.json_loads_success,
                "schema_valid": parse_report.schema_validation_success,
                "retry_performed": parse_report.retry_performed,
                "final_status": parse_report.final_status,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Save artifacts
            self.log("Step 6: Saving artifacts...")
            self._save_artifacts(result)
            
            self.log(f"\n=== DIAGNOSTIC COMPLETE ===")
            self.log(f"Final Status: {parse_report.final_status}")
            self.log(f"Output Directory: {self.output_dir}")
            
            # Print full content if requested
            if self.config.print_full_response:
                print("\n" + "="*80)
                print("FULL RAW RESPONSE CONTENT:")
                print("="*80)
                print(response_bundle.raw_content)
                print("="*80 + "\n")
            
            if self.config.print_full_request:
                print("\n" + "="*80)
                print("FULL REQUEST PAYLOAD (SANITIZED):")
                print("="*80)
                print(json.dumps(request_bundle.full_payload, indent=2, default=str))
                print("="*80 + "\n")
            
            return result
            
        except Exception as e:
            self.log(f"FATAL ERROR: {e}")
            traceback.print_exc()
            result.parse_report = ParseReport(
                final_status="fatal_error",
                summary=str(e)
            )
            return result
        finally:
            try:
                next(session_gen, None)
            except StopIteration:
                pass
    
    def _build_solve_request(
        self, 
        profile: PromptProfile, 
        token_policy: TokenPolicy,
        question: str
    ) -> Tuple[RequestBundle, Dict[str, Any]]:
        """Build the exact OpenAI request we use in production."""
        
        # Get system prompt with fallback
        system_prompt = profile.system_prompt_content
        if not system_prompt:
            self.log("  [WARN] Profile has no system_prompt_content, using fallback")
            system_prompt = """You are a skilled math tutor. Solve the given problem step by step.
Output your response as valid JSON matching the schema provided.
Be concise but thorough. Show your work clearly."""
        
        # Get and process schema
        json_schema_config = profile.json_schema_content
        if not isinstance(json_schema_config, dict) or not json_schema_config:
            json_schema_config = get_json_schema_for_openai_v3()
        
        if "schema" in json_schema_config and isinstance(json_schema_config["schema"], dict):
            json_schema_config = json_schema_config["schema"]
        
        try:
            deref_schema = deref_json_schema(json_schema_config)
        except Exception:
            deref_schema = deref_json_schema(get_json_schema_for_openai_v3())
        
        deref_schema = enforce_strict(deref_schema)
        if deref_schema.get("type") is None:
            deref_schema["type"] = "object"
        
        # Build user message
        trusted_context = {
            "learning_mode": self.config.learning,
            "requested_mode": self.config.detail
        }
        normalized_ctx = normalize_trusted_context(trusted_context)
        normalized_ctx["requested_mode"] = self.config.detail
        user_message = build_compact_user_message(question, normalized_ctx)
        
        # Determine max tokens
        if self.config.detail == "minimal":
            if self.config.learning == "solve":
                max_tokens = token_policy.text_output_minimal_solve
            else:
                max_tokens = token_policy.text_output_minimal_study
        else:
            if self.config.learning == "solve":
                max_tokens = token_policy.text_output_detailed_solve
            else:
                max_tokens = token_policy.text_output_detailed_study
        
        # Build raw params based on model type
        if "gpt-5" in self.model.lower():
            # Use responses.create format
            verbosity = "low" if self.config.detail == "minimal" else "high"
            raw_params = {
                "model": self.model,
                "input": [
                    {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                    {"role": "user", "content": [{"type": "input_text", "text": user_message}]}
                ],
                "text": {
                    "verbosity": verbosity,
                    "format": {
                        "type": "json_schema",
                        "name": "solve_response_v3",
                        "schema": deref_schema,
                        "strict": True
                    }
                },
                "max_output_tokens": max_tokens
            }
        else:
            # Use chat.completions format
            raw_params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "solve_response_v3",
                        "strict": True,
                        "schema": deref_schema
                    }
                },
                "max_completion_tokens": max_tokens
            }
        
        # Build request bundle
        bundle = RequestBundle(
            model=self.model,
            max_output_tokens=max_tokens,
            reasoning_effort=None,
            system_prompt_length=len(system_prompt),
            system_prompt_preview=system_prompt[:500] if len(system_prompt) > 500 else system_prompt,
            user_message_length=len(user_message),
            user_message_content=user_message,
            schema_name="solve_response_v3",
            schema_object=deref_schema,
            tool_definitions=None,
            full_payload=redact_secrets(raw_params),
            timestamp=datetime.utcnow().isoformat()
        )
        
        return bundle, raw_params
    
    async def _call_openai(self, params: Dict[str, Any]) -> ResponseBundle:
        """Call OpenAI and capture FULL response."""
        bundle = ResponseBundle(timestamp=datetime.utcnow().isoformat())
        
        try:
            if "gpt-5" in self.model.lower():
                # Use responses.create
                response = await self.client.responses.create(**params)
                
                # Extract content
                content = None
                if hasattr(response, "output") and response.output:
                    for item in response.output:
                        if hasattr(item, "content") and item.content:
                            content = item.content[0].text
                            break
                
                bundle.raw_content = content or ""
                bundle.content_length = len(bundle.raw_content)
                bundle.content_preview_head = bundle.raw_content[:500]
                bundle.content_preview_tail = bundle.raw_content[-500:] if len(bundle.raw_content) > 500 else ""
                
                # Status
                bundle.status = getattr(response, "status", "completed")
                bundle.finish_reason = None  # Responses API doesn't have finish_reason
                bundle.incomplete_details = getattr(response, "incomplete_details", None)
                if bundle.incomplete_details:
                    bundle.incomplete_details = asdict(bundle.incomplete_details) if hasattr(bundle.incomplete_details, '__dict__') else dict(bundle.incomplete_details)
                
                # Usage
                if hasattr(response, "usage"):
                    bundle.input_tokens = getattr(response.usage, "input_tokens", 0) or getattr(response.usage, "prompt_tokens", 0)
                    bundle.output_tokens = getattr(response.usage, "output_tokens", 0) or getattr(response.usage, "completion_tokens", 0)
                    bundle.total_tokens = getattr(response.usage, "total_tokens", 0)
                    if hasattr(response.usage, "input_token_details"):
                        bundle.cached_tokens = getattr(response.usage.input_token_details, "cached_tokens", 0)
                    elif hasattr(response.usage, "prompt_tokens_details"):
                        bundle.cached_tokens = getattr(response.usage.prompt_tokens_details, "cached_tokens", 0)
                
                # Request ID
                bundle.request_id = getattr(response, "id", None)
                
                # Full response dict
                try:
                    bundle.full_response_dict = response.model_dump() if hasattr(response, "model_dump") else {}
                except Exception:
                    bundle.full_response_dict = {"raw": str(response)}
                
            else:
                # Use chat.completions
                response = await self.client.chat.completions.create(**params)
                
                bundle.raw_content = response.choices[0].message.content or ""
                bundle.content_length = len(bundle.raw_content)
                bundle.content_preview_head = bundle.raw_content[:500]
                bundle.content_preview_tail = bundle.raw_content[-500:] if len(bundle.raw_content) > 500 else ""
                
                bundle.status = "completed"
                bundle.finish_reason = response.choices[0].finish_reason
                
                if bundle.finish_reason == "length":
                    bundle.incomplete_details = {"reason": "max_tokens_exceeded"}
                
                if hasattr(response, "usage"):
                    bundle.input_tokens = response.usage.prompt_tokens
                    bundle.output_tokens = response.usage.completion_tokens
                    bundle.total_tokens = response.usage.total_tokens
                    if hasattr(response.usage, "prompt_tokens_details") and response.usage.prompt_tokens_details:
                        bundle.cached_tokens = getattr(response.usage.prompt_tokens_details, "cached_tokens", 0)
                
                bundle.request_id = response.id
                
                try:
                    bundle.full_response_dict = response.model_dump() if hasattr(response, "model_dump") else {}
                except Exception:
                    bundle.full_response_dict = {"raw": str(response)}
                    
        except Exception as e:
            bundle.status = "error"
            bundle.error = {"type": type(e).__name__, "message": str(e)}
            bundle.raw_content = ""
        
        return bundle
    
    def _parse_and_validate(self, content: str, profile: PromptProfile) -> ParseReport:
        """Parse and validate response content."""
        report = ParseReport(
            extracted_content_length=len(content),
            content_head_500=content[:500] if content else "",
            content_tail_500=content[-500:] if len(content) > 500 else ""
        )
        
        if not content:
            report.json_loads_success = False
            report.json_loads_error = "Empty content"
            return report
        
        # Step 1: JSON parse
        try:
            parsed = json.loads(content)
            report.json_loads_success = True
        except json.JSONDecodeError as e:
            report.json_loads_success = False
            report.json_loads_error = str(e)
            report.json_error_position = e.pos
            
            # Context around error
            start = max(0, e.pos - 120)
            end = min(len(content), e.pos + 120)
            report.json_error_context = content[start:end]
            return report
        
        # Step 2: Schema validation
        try:
            validation = validate_response(parsed, strict=True)
            if validation.valid:
                report.schema_validation_success = True
            else:
                report.schema_validation_success = False
                report.schema_validation_errors = [
                    {"path": err.get("path", ""), "message": err.get("message", str(err))}
                    for err in (validation.errors if hasattr(validation, 'errors') else [])
                ]
        except Exception as e:
            report.schema_validation_success = False
            report.schema_validation_errors = [{"path": "", "message": str(e)}]
        
        return report
    
    def _save_artifacts(self, result: DiagnosticResult):
        """Save all artifacts to output directory."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # request_sanitized.json
        if result.request:
            with open(self.output_dir / "request_sanitized.json", "w") as f:
                json.dump(asdict(result.request), f, indent=2, default=str)
        
        # response_raw.json
        if result.response:
            with open(self.output_dir / "response_raw.json", "w") as f:
                json.dump(asdict(result.response), f, indent=2, default=str)
        
        # extracted_content.txt
        if result.response:
            with open(self.output_dir / "extracted_content.txt", "w", encoding="utf-8") as f:
                f.write(result.response.raw_content)
        
        # parse_report.json
        if result.parse_report:
            with open(self.output_dir / "parse_report.json", "w") as f:
                json.dump(asdict(result.parse_report), f, indent=2, default=str)
        
        # telemetry.json
        with open(self.output_dir / "telemetry.json", "w") as f:
            json.dump(result.telemetry, f, indent=2, default=str)
        
        # summary.md
        self._write_summary(result)
    
    def _write_summary(self, result: DiagnosticResult):
        """Write human-readable summary."""
        lines = [
            f"# OpenAI Debug Harness Run: {result.run_id}",
            "",
            "## Configuration",
            f"- Mode: {self.config.mode}",
            f"- Detail: {self.config.detail}",
            f"- Learning: {self.config.learning}",
            f"- Question: `{self.config.question}`",
            "",
            "## Request",
        ]
        
        if result.request:
            lines.extend([
                f"- Model: `{result.request.model}`",
                f"- Max Output Tokens: {result.request.max_output_tokens}",
                f"- System Prompt Length: {result.request.system_prompt_length} chars",
                f"- User Message Length: {result.request.user_message_length} chars",
                f"- Schema: `{result.request.schema_name}`",
            ])
        
        lines.append("")
        lines.append("## Response")
        
        if result.response:
            lines.extend([
                f"- Status: `{result.response.status}`",
                f"- Finish Reason: `{result.response.finish_reason}`",
                f"- Latency: {result.response.latency_ms}ms",
                f"- Input Tokens: {result.response.input_tokens}",
                f"- Output Tokens: {result.response.output_tokens}",
                f"- Total Tokens: {result.response.total_tokens}",
                f"- Cached Tokens: {result.response.cached_tokens}",
                f"- Content Length: {result.response.content_length} chars",
            ])
            
            if result.response.incomplete_details:
                lines.append(f"- Incomplete Details: `{result.response.incomplete_details}`")
        
        lines.append("")
        lines.append("## Parsing")
        
        if result.parse_report:
            lines.extend([
                f"- JSON Parse: {'✅ SUCCESS' if result.parse_report.json_loads_success else '❌ FAILED'}",
                f"- Schema Valid: {'✅ SUCCESS' if result.parse_report.schema_validation_success else '❌ FAILED'}",
                f"- Final Status: `{result.parse_report.final_status}`",
            ])
            
            if result.parse_report.json_loads_error:
                lines.append(f"- JSON Error: `{result.parse_report.json_loads_error}`")
            
            if result.parse_report.schema_validation_errors:
                lines.append("- Schema Errors:")
                for err in result.parse_report.schema_validation_errors[:5]:
                    lines.append(f"  - `{err.get('path', '')}`: {err.get('message', '')}")
            
            if result.parse_report.retry_performed:
                lines.extend([
                    "",
                    "## Retry",
                    f"- Reason: {result.parse_report.retry_reason}",
                    f"- Success: {'✅' if result.parse_report.retry_success else '❌'}",
                ])
        
        lines.extend([
            "",
            "## Summary",
            f"{result.parse_report.summary if result.parse_report else 'N/A'}",
        ])
        
        with open(self.output_dir / "summary.md", "w") as f:
            f.write("\n".join(lines))


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="OpenAI Debug Harness - Test API calls with full request/response capture"
    )
    
    parser.add_argument("--mode", choices=["solve", "extract"], default="solve",
                        help="Operation mode: solve or extract")
    parser.add_argument("--detail", choices=["minimal", "detailed"], default="minimal",
                        help="Detail level for solve mode")
    parser.add_argument("--learning", choices=["solve", "study"], default="solve",
                        help="Learning mode for solve")
    parser.add_argument("--question", type=str, default="Solve for x: x^2 - 5x + 6 = 0",
                        help="Math question to solve")
    parser.add_argument("--user_id", type=int, default=2,
                        help="User ID for profile resolution")
    parser.add_argument("--source", choices=["image", "pdf"], default="image",
                        help="Source type for extract mode")
    parser.add_argument("--file", type=str, default="",
                        help="File path for extract mode")
    parser.add_argument("--outdir", type=str, default="app/storage/debug/openai",
                        help="Output directory for artifacts")
    parser.add_argument("--redact_input", type=str, default="true",
                        help="Redact input in logs (true/false)")
    parser.add_argument("--redact_ocr", type=str, default="true",
                        help="Redact OCR text in logs (true/false)")
    parser.add_argument("--print_full_response", type=str, default="true",
                        help="Print full response to console (true/false)")
    parser.add_argument("--print_full_request", type=str, default="true",
                        help="Print full request to console (true/false)")
    parser.add_argument("--trace", type=str, default="true",
                        help="Enable verbose logging (true/false)")
    
    args = parser.parse_args()
    
    config = HarnessConfig(
        mode=args.mode,
        detail=args.detail,
        learning=args.learning,
        question=args.question,
        user_id=args.user_id,
        source=args.source,
        file_path=args.file,
        outdir=args.outdir,
        redact_input=args.redact_input.lower() == "true",
        redact_ocr=args.redact_ocr.lower() == "true",
        print_full_response=args.print_full_response.lower() == "true",
        print_full_request=args.print_full_request.lower() == "true",
        trace=args.trace.lower() == "true"
    )
    
    harness = DebugHarness(config)
    
    if args.mode == "solve":
        result = asyncio.run(harness.run_solve())
    else:
        print("Extract mode not yet implemented")
        return
    
    print("\n" + "="*80)
    print("DIAGNOSTIC COMPLETE")
    print("="*80)
    print(f"Run ID: {result.run_id}")
    print(f"Output: {harness.output_dir}")
    print(f"Status: {result.parse_report.final_status if result.parse_report else 'unknown'}")
    print("="*80)


if __name__ == "__main__":
    main()
