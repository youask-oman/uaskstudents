"""
Script to show exactly what prompts and schemas would be sent to OpenAI
for user student334@uask.ai with different Goal/AnswerStyle combinations.
"""
import json
from app.database import get_session
from app.models import User
from app.llm_profiles.profile_resolver import ProfileResolver

def main():
    session = next(get_session())
    user = session.get(User, 334)
    
    question = "expand(x−1)((x−1)(x^2+x+1)+x+1)"
    
    print("=" * 80)
    print("USER: student334@uask.ai (user_id=334)")
    print("PLAN: student_standard")
    print(f"QUESTION: {question}")
    print("=" * 80)
    
    # =========================================================================
    # SCENARIO 1: Goal=Solve, AnswerStyle=Tutor -> detailed mode
    # =========================================================================
    print("\n" + "=" * 80)
    print("SCENARIO 1: Goal=Solve + AnswerStyle=Tutor")
    print("-> requested_mode='detailed', learning_mode='solve'")
    print("=" * 80)
    
    profile1 = ProfileResolver.resolve_profile(
        session, user, 
        requested_mode='detailed', 
        learning_mode='solve'
    )
    
    print(f"\n[RESOLVED PROFILE]")
    print(f"  Tier: {profile1.tier}")
    print(f"  Mode: {profile1.mode}")
    print(f"  Max Output Tokens: {profile1.max_output_tokens}")
    print(f"  Max Steps: {profile1.max_steps}")
    
    print("\n" + "-" * 80)
    print("SYSTEM PROMPT (sent to OpenAI):")
    print("-" * 80)
    print(profile1.system_prompt_content)
    
    print("\n" + "-" * 80)
    print("JSON SCHEMA (sent to OpenAI response_format):")
    print("-" * 80)
    schema1 = profile1.json_schema_content
    print(json.dumps(schema1, indent=2)[:4000])
    if len(json.dumps(schema1)) > 4000:
        print("\n... [TRUNCATED - full schema is", len(json.dumps(schema1)), "chars]")
    
    # =========================================================================
    # SCENARIO 2: Goal=Study, AnswerStyle=Tutor -> detailed mode with study learning
    # =========================================================================
    print("\n\n" + "=" * 80)
    print("SCENARIO 2: Goal=Study + AnswerStyle=Tutor")
    print("-> requested_mode='detailed', learning_mode='study'")
    print("=" * 80)
    
    profile2 = ProfileResolver.resolve_profile(
        session, user, 
        requested_mode='detailed', 
        learning_mode='study'
    )
    
    print(f"\n[RESOLVED PROFILE]")
    print(f"  Tier: {profile2.tier}")
    print(f"  Mode: {profile2.mode}")
    print(f"  Max Output Tokens: {profile2.max_output_tokens}")
    print(f"  Max Steps: {profile2.max_steps}")
    
    print("\n[NOTE] The system prompt and schema are the SAME as Scenario 1.")
    print("The difference is in the trusted_context.learning_mode field sent in the request,")
    print("which the solver uses to adjust step granularity and include more checkpoints.")
    
    # =========================================================================
    # Show what the full request payload would look like
    # =========================================================================
    print("\n\n" + "=" * 80)
    print("EXAMPLE SOLVE REQUEST PAYLOAD (what frontend sends):")
    print("=" * 80)
    
    example_payload = {
        "confirmed_text": question,
        "confirmed_markdown": question,
        "mode": "detailed",
        "requested_mode": "detailed",
        "trusted_context": {
            "learning_mode": "study",  # or "solve"
            "grade_level": "Grade 11",
            "region_country": "Canada",
            "region_state_province": "ON"
        },
        "features_used": {
            "ocr_used": False,
            "voice_used": False
        },
        "subject": "Mathematics",
        "difficulty": "High School / AP"
    }
    
    print(json.dumps(example_payload, indent=2))

if __name__ == "__main__":
    main()
