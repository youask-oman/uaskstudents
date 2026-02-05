import os
import sys
sys.path.insert(0, '.')
os.environ['DATABASE_URL'] = 'sqlite:///./uaskstudents.db'

from sqlmodel import Session, select, create_engine
from app.models import PromptTemplateEntry

engine = create_engine(os.environ['DATABASE_URL'])
with Session(engine) as session:
    print('=== All Active Prompts ===')
    prompts = session.exec(
        select(PromptTemplateEntry).where(PromptTemplateEntry.is_active == True)
    ).all()
    
    for p in prompts:
        print(f'{p.prompt_id} | tier={p.tier} | mode={p.mode} | role={p.role}')
    
    print('\n=== Looking for Free-form Prompts ===')
    freeform_ids = [
        'free_form_math_standard_detailed_v1',
        'free_form_math_free_fast_v1',
        'free_form_math_research_rigorous_v1'
    ]
    
    for pid in freeform_ids:
        p = session.exec(
            select(PromptTemplateEntry).where(
                PromptTemplateEntry.prompt_id == pid,
                PromptTemplateEntry.is_active == True
            )
        ).first()
        status = 'EXISTS' if p else 'MISSING'
        print(f'{pid}: {status}')
