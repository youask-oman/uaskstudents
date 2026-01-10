from sqlmodel import Session, select, SQLModel
from app.database import engine, create_db_and_tables
from app.models import User, ChatSession, ChatMessage, UsageLog
from app.auth import get_password_hash
from datetime import datetime, timedelta

def active_seed():
    # Force reset of schema to ensure new columns exist (Dev only!)
    SQLModel.metadata.drop_all(engine)
    create_db_and_tables()
    
    with Session(engine) as session:
        # Check if main admin exists, if so, we assume db is seeded (or we can opt to wipe/re-seed if needed, but safe check first)
        # Check if one of the new students exists to determine if we need to seed
        existing_new_student = session.exec(select(User).where(User.email == "sarah.m@uni.edu")).first()
        if existing_new_student:
            print("Expanded seed data already exists. Skipping.")
            return

        print("Seeding database...")

        # --- create Admin ---
        admin = User(
            email="admin@uask.ai",
            full_name="System Admin",
            password_hash=get_password_hash("admin123"),  # Default password: admin123
            role="admin",
            subscription_tier="enterprise",
            subscription_status="active",
            subscription_expiry=datetime.utcnow() + timedelta(days=3650), # 10 years
            avatar_url="https://ui-avatars.com/api/?name=System+Admin&background=0D8ABC&color=fff",
            is_verified=True
        )
        session.add(admin)

        # --- Create 10 Students ---
        students = []
        student_data = [
            ("student@uask.ai", "Alex Student", "pro", "active"),
            ("sarah.m@uni.edu", "Sarah Miller", "free", "active"),
            ("j.chen@tech.edu", "James Chen", "pro", "active"),
            ("emma.w@college.edu", "Emma Wilson", "free", "active"),
            ("michael.b@uask.ai", "Michael Brown", "pro", "cancelled"),
            ("lisa.taylor@uni.edu", "Lisa Taylor", "free", "active"),
            ("david.zhang@tech.edu", "David Zhang", "pro", "active"),
            ("rachel.green@college.edu", "Rachel Green", "free", "active"),
            ("sam.wilson@uask.ai", "Sam Wilson", "pro", "past_due"),
            ("olivia.jones@uni.edu", "Olivia Jones", "free", "active")
        ]

        for email, name, tier, sub_status in student_data:
            expiry = datetime.utcnow() + timedelta(days=30) if tier == 'pro' else None
            s = User(
                email=email,
                full_name=name,
                password_hash=get_password_hash("student123"),  # Default password: student123
                role="student",
                academic_level="Undergraduate",
                subscription_tier=tier,
                subscription_status=sub_status,
                subscription_expiry=expiry,
                avatar_url=f"https://ui-avatars.com/api/?name={name.replace(' ', '+')}&background=random",
                is_verified=True
            )
            session.add(s)
            students.append(s)
        
        session.commit()
        
        # Reload student@uask.ai to map sessions
        main_student = session.exec(select(User).where(User.email == "student@uask.ai")).first()

        # --- Create Configuration / Metadata (Simulated via ChatSessions for now as we don't have Config tables defined yet) ---
        # In a real app we might have a 'Subject' or 'Configuration' table. 
        # For now, we seed chat sessions to represent "Content" being present.

        # Session 1: Physics
        s1 = ChatSession(
            user_id=main_student.id,
            title="Projectile Motion Problem",
            subject="Physics",
            topic="Kinematics",
            created_at=datetime.utcnow() - timedelta(days=1)
        )
        session.add(s1)
        session.commit()
        session.refresh(s1)

        session.add(ChatMessage(session_id=s1.id, role="user", content="Analyze the trajectory of a ball thrown at 45 degrees.", media_url="https://example.com/ball.jpg"))
        
        physics_structured = {
            "problem": {
                "goal": "Analyze Projectile Motion",
                "latex": "v_0 = 25m/s, \\theta = 45^\\circ"
            },
            "solution": {
                "steps": [
                    {
                        "index": 1,
                        "title": "Initial Components",
                        "explanation": "Break the initial velocity vector into horizontal and vertical components using trigonometry.",
                        "math": {
                            "latex_lines": [
                                "v_{0x} = v_0 \\cos(45^\\circ) = 25 \\cdot \\frac{\\sqrt{2}}{2} \\approx 17.68 \\text{ m/s}",
                                "v_{0y} = v_0 \\sin(45^\\circ) = 25 \\cdot \\frac{\\sqrt{2}}{2} \\approx 17.68 \\text{ m/s}"
                            ]
                        }
                    },
                    {
                        "index": 2,
                        "title": "Time of Flight",
                        "explanation": "Calculate the time it takes for the ball to return to the ground (where $y=0$).",
                        "math": {
                            "latex_lines": [
                                "y = v_{0y}t - \\frac{1}{2}gt^2",
                                "0 = 17.68t - 4.9t^2 \\implies t \\approx 3.61 \\text{ s}"
                            ]
                        }
                    }
                ],
                "final_answer": "R = 63.7m, t = 3.61s"
            },
            "verification": {
                "methods_used": [
                    {
                        "method": "Range Formula",
                        "description": "Cross-check with standard range formula $R = \\frac{v_0^2 \\sin(2\\theta)}{g}$",
                        "work": {
                            "latex_lines": ["R = \\frac{25^2 \\sin(90^\\circ)}{9.8} = 63.77 \\text{ m}"]
                        },
                        "conclusion": "Pass"
                    }
                ]
            },
            "concepts": [
                {
                    "title": "Projectile Motion",
                    "category": "Physics",
                    "description": "Form of motion experienced by an object thrown near the Earth's surface.",
                    "tags": ["Kinematics", "Mechanics"]
                }
            ]
        }

        session.add(ChatMessage(
            session_id=s1.id, 
            role="assistant", 
            content="The optimal angle for maximum range is 45 degrees in a vacuum.", 
            structured_data=physics_structured
        ))

        # Session 2: Calculus
        s2 = ChatSession(
            user_id=main_student.id,
            title="Derivatives of Trig Functions",
            subject="Mathematics",
            topic="Calculus",
            created_at=datetime.utcnow() - timedelta(hours=5)
        )
        session.add(s2)
        
        # Session 3: Chemistry
        s3 = ChatSession(
            user_id=main_student.id,
            title="Balancing Redox Reactions",
            subject="Chemistry",
            topic="Inorganic",
            created_at=datetime.utcnow() - timedelta(minutes=30)
        )
        session.add(s3)

        # Logs
        session.add(UsageLog(user_id=main_student.id, action_type="login", tokens_used=0))
        session.add(UsageLog(user_id=main_student.id, action_type="solve_request", tokens_used=120))

        session.commit()
        print("Database seeded successfully with 10 students and sample data!")

if __name__ == "__main__":
    active_seed()
