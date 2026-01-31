"""
Add WhatsApp-specific prompt template to the database
This prompt is optimized for mobile WhatsApp messaging format
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.database import engine, Session
from app.models import PromptTemplate, PromptVersion
from datetime import datetime

def add_whatsapp_prompt():
    """Add WhatsApp-specific prompt template"""
    
    whatsapp_prompt = """You are a friendly WhatsApp math tutor helping students solve problems on their mobile phones.

IMPORTANT GUIDELINES:
1. Keep responses CONCISE and MOBILE-FRIENDLY (under 500 words)
2. Use simple text formatting (no complex LaTeX on WhatsApp)
3. Break down steps into short, digestible chunks
4. Use emojis sparingly to make it engaging: 📝 ✅ ⚠️ 🎯
5. For complex equations, describe the approach rather than showing full LaTeX

RESPONSE FORMAT:
📝 *Problem:* [restate briefly]

*Solution Steps:*
1. *[Step Title]*
   [Brief explanation]
   
2. *[Next Step]*
   [Brief explanation]

✅ *Final Answer:* [concise answer]

RULES:
- If the problem is too complex for WhatsApp format, suggest they use the web app
- Always be encouraging and supportive
- Use simple language appropriate for mobile messaging
- Focus on understanding over notation
- If student sends photo, acknowledge it and extract the problem text

OUTPUT: Plain text only, optimized for mobile WhatsApp chat."""

    with Session(engine) as session:
        # Check if whatsapp-solver template already exists
        from sqlmodel import select
        existing = session.exec(
            select(PromptTemplate).where(PromptTemplate.slug == "whatsapp-solver")
        ).first()
        
        if existing:
            print("WhatsApp solver prompt already exists. Updating...")
            
            # Get current version number
            versions = session.exec(
                select(PromptVersion).where(PromptVersion.template_id == existing.id)
            ).all()
            
            # Determine next version
            if versions:
                # Parse version strings like "v1.0.0" to get the major version
                max_version = max([int(v.version.split('.')[0].replace('v', '')) for v in versions])
                next_version = f"v{max_version + 1}.0.0"
            else:
                next_version = "v1.0.0"
            
            # Create new version
            new_version = PromptVersion(
                template_id=existing.id,
                version=next_version,
                content=whatsapp_prompt,
                author="system",
                is_production=True
            )
            
            # Deactivate old versions
            for v in versions:
                v.is_production = False
            
            session.add(new_version)
            session.commit()
            print(f"✓ Updated WhatsApp prompt to {next_version}")
        else:
            print("Creating new WhatsApp solver prompt template...")
            
            # Create template
            template = PromptTemplate(
                name="WhatsApp Math Solver",
                slug="whatsapp-solver",
                category="solver",
                description="Mobile-optimized prompt for WhatsApp bot math solving",
                current_version=1,
                is_system=True,
                created_by="system"
            )
            session.add(template)
            session.flush()
            
            # Create first version
            version = PromptVersion(
                template_id=template.id,
                version="v1.0.0",
                content=whatsapp_prompt,
                author="system",
                is_production=True
            )
            session.add(version)
            session.commit()
            print("✓ Created WhatsApp solver prompt template")
        
        print("\nWhatsApp prompt setup complete!")
        print("The bot will now use this optimized prompt for mobile conversations.")

if __name__ == "__main__":
    add_whatsapp_prompt()
