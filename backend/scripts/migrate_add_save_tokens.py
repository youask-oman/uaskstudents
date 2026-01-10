"""
Migration script to add token tracking and save functionality fields
Run this after updating models.py
"""
from sqlmodel import Session, SQLModel
from app.database import engine, create_db_and_tables
from app.models import User, ChatSession
from datetime import datetime

def migrate():
    print("Starting migration: Adding token tracking and save fields...")
    
    # This will add the new columns to existing tables
    # SQLModel will handle adding new fields automatically
    SQLModel.metadata.create_all(engine)
    
    # Update existing users to have token tracking initialized
    with Session(engine) as session:
        users = session.query(User).all()
        for user in users:
            if not hasattr(user, 'tokens_used_this_month') or user.tokens_used_this_month is None:
                user.tokens_used_this_month = 0
            if not hasattr(user, 'last_token_reset') or user.last_token_reset is None:
                user.last_token_reset = datetime.utcnow()
        
        # Update existing chat sessions to be unsaved by default
        chat_sessions = session.query(ChatSession).all()
        for chat_session in chat_sessions:
            if not hasattr(chat_session, 'is_saved') or chat_session.is_saved is None:
                chat_session.is_saved = False
        
        session.commit()
        print(f"✅ Updated {len(users)} users with token tracking")
        print(f"✅ Updated {len(chat_sessions)} chat sessions with save status")
    
    print("Migration completed successfully!")

if __name__ == "__main__":
    migrate()
