import csv
from pathlib import Path
from typing import Optional
from sqlmodel import Session, select, SQLModel
from app.database import engine, create_db_and_tables
from app.models import User, ChatSession, ChatMessage, UsageLog, Plan, School, Subscription, UsageLedger, SchoolImportRun
from app.auth import get_password_hash
from datetime import datetime, timedelta
import hashlib
import random

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

        # --- Seed Plans ---
        plan_data = [
            {
                "name": "Free",
                "slug": "free",
                "credits_per_month": 50,
                "price_monthly_cents": 0,
                "price_yearly_cents": 0,
                "features": {
                    "ocr_monthly_cap": 3,
                    "voice_monthly_cap": 3,
                    "daily_credit_cap": 5
                },
                "multipliers": {
                    "text_concise": 1,
                    "text_detailed": 1000,
                    "ocr_add": 1,
                    "voice_add": 1
                }
            },
            {
                "name": "Student Standard",
                "slug": "student_standard",
                "credits_per_month": 300,
                "price_monthly_cents": 999,
                "price_yearly_cents": 9900,
                "features": {
                    "ocr_monthly_cap": 100,
                    "voice_monthly_cap": 50,
                    "daily_credit_cap": 50
                },
                "multipliers": {
                    "text_concise": 1,
                    "text_detailed": 2,
                    "ocr_add": 1,
                    "voice_add": 1
                }
            },
            {
                "name": "Family Standard",
                "slug": "family_standard",
                "credits_per_month": 600,
                "price_monthly_cents": 1999,
                "price_yearly_cents": 19900,
                "features": {
                    "ocr_monthly_cap": 200,
                    "voice_monthly_cap": 100,
                    "daily_credit_cap": 100
                },
                "multipliers": {
                    "text_concise": 1,
                    "text_detailed": 2,
                    "ocr_add": 1,
                    "voice_add": 1
                }
            },
            {
                "name": "Enterprise",
                "slug": "enterprise",
                "credits_per_month": 1000,
                "price_monthly_cents": 4999,
                "price_yearly_cents": 49900,
                "features": {
                    "ocr_monthly_cap": 500,
                    "voice_monthly_cap": 250,
                    "daily_credit_cap": 200
                },
                "multipliers": {
                    "text_concise": 1,
                    "text_detailed": 1,
                    "ocr_add": 1,
                    "voice_add": 1
                }
            }
        ]
        plans = {}
        for plan_def in plan_data:
            plan = Plan(
                name=plan_def["name"],
                slug=plan_def["slug"],
                credits_per_month=plan_def["credits_per_month"],
                price_monthly_cents=plan_def["price_monthly_cents"],
                price_yearly_cents=plan_def["price_yearly_cents"],
                seats=1,
                features=plan_def["features"],
                multipliers=plan_def["multipliers"],
                is_active=True
            )
            session.add(plan)
            session.commit()
            plans[plan.slug] = plan

        # --- Seed Schools ---
        school_names = [
            ("Cascade STEM Academy", "USA", "WA"),
            ("Maple Grove High", "Canada", "ON"),
            ("Summit Engineering Prep", "USA", "CA"),
        ]
        schools = []
        for name, country, state in school_names:
            key = f"{country.lower()}|{state.lower()}|{name.lower()}"
            school = School(
                country=country,
                province_state=state,
                school_name=name,
                source="seed",
                school_key=hashlib.sha256(key.encode("utf-8")).hexdigest()
            )
            session.add(school)
            session.commit()
            schools.append(school)

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

        school_count = len(schools)
        for idx, (email, name, tier, sub_status) in enumerate(student_data):
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
            if school_count:
                s.school_id = schools[idx % school_count].id
            session.add(s)
            students.append(s)
        
        session.commit()

        def plan_for_tier(tier):
            mapping = {"free": "free", "pro": "student_standard", "family": "family_standard", "enterprise": "enterprise"}
            return mapping.get(tier, "free")

        def create_subscription_for(user_obj, plan_slug):
            plan = plans.get(plan_slug)
            if not plan:
                return None
            sub = Subscription(
                user_id=user_obj.id,
                plan_id=plan.id,
                status="active",
                current_period_start=datetime.utcnow(),
                current_period_end=datetime.utcnow() + timedelta(days=30),
                credits_balance=float(plan.credits_per_month),
                credits_used_this_period=0.0
            )
            session.add(sub)
            session.commit()
            session.add(UsageLedger(
                subscription_id=sub.id,
                transaction_type="INIT",
                amount=0.0,
                balance_after=sub.credits_balance,
                reference_id="seed_init",
                meta={"note": "Seed subscription"}
            ))
            session.commit()
            return sub

        # --- Seed 500 Random Students ---
        first_names = ["Aiden","Mia","Noah","Luna","Ethan","Ava","Logan","Zoe","Elijah","Harper","Lucas","Chloe","Oliver","Amelia","Liam","Scarlett","Mason","Isla","Leo","Aria"]
        last_names = ["Taylor","Brown","Lee","Wilson","Patel","Garcia","Chen","Martin","Robinson","Walker","Harris","Hall","Allen","Young","King","Wright","Scott","Torres","Nguyen","Hill"]
        tier_choices = ["free","pro","family"]
        extra_students = []
        for i in range(1, 501):
            first = random.choice(first_names)
            last = random.choice(last_names)
            name = f"{first} {last}"
            email = f"{first.lower()}.{last.lower()}{i}@iasnap.com"
            tier = random.choice(tier_choices)
            status = "active" if tier != "pro" or random.random() > 0.2 else "past_due"
            school = random.choice(schools) if schools else None
            expiry = datetime.utcnow() + timedelta(days=30) if tier == 'pro' else None
            s = User(
                email=email,
                full_name=name,
                password_hash=get_password_hash("student123"),
                role="student",
                academic_level="High School",
                subscription_tier=tier,
                subscription_status=status,
                subscription_expiry=expiry,
                avatar_url=f"https://ui-avatars.com/api/?name={first.replace(' ','+')}+{last.replace(' ','+')}+{i}&background=random",
                is_verified=True,
                profile_country=school.country if school else "USA",
                profile_province_state=school.province_state if school else "CA",
                school_id=school.id if school else None
            )
            session.add(s)
            extra_students.append(s)
        session.commit()

        for student in extra_students:
            session.refresh(student)
            create_subscription_for(student, plan_for_tier(student.subscription_tier))

        def create_subscription_for(user_obj, plan_slug):
            plan = plans.get(plan_slug)
            if not plan:
                return None
            sub = Subscription(
                user_id=user_obj.id,
                plan_id=plan.id,
                status="active",
                current_period_start=datetime.utcnow(),
                current_period_end=datetime.utcnow() + timedelta(days=30),
                credits_balance=float(plan.credits_per_month),
                credits_used_this_period=0.0
            )
            session.add(sub)
            session.commit()
            session.add(UsageLedger(
                subscription_id=sub.id,
                transaction_type="INIT",
                amount=0.0,
                balance_after=sub.credits_balance,
                reference_id="seed_init",
                meta={"note": "Seed subscription"}
            ))
            session.commit()
            return sub

        def plan_for_tier(tier):
            mapping = {"free": "free", "pro": "student_standard", "family": "family_standard", "enterprise": "enterprise"}
            return mapping.get(tier, "free")

        # Create subscriptions for admin + students
        session.refresh(admin)
        create_subscription_for(admin, plan_for_tier(admin.subscription_tier))
        for student in students:
            session.refresh(student)
            create_subscription_for(student, plan_for_tier(student.subscription_tier))
        
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

        load_school_directory(session)

def _clean_string(value: Optional[str]) -> str:
    if value is None:
        return ""
    return str(value).strip()

def _compute_school_key(country: str, province: str, city: str, name: str) -> str:
    normalized = "|".join([
        country.strip().lower(),
        province.strip().lower(),
        city.strip().lower() if city else "",
        name.strip().lower()
    ])
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def import_school_csv(session: Session, path: Path, country: str, source_label: str, column_map: dict) -> dict:
    stats = {
        "processed": 0,
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0
    }

    if not path.exists():
        return stats

    with path.open(newline="", encoding="utf-8", errors="replace") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            stats["processed"] += 1
            try:
                name = _clean_string(row.get(column_map["name"]))
                province = _clean_string(row.get(column_map["province"]))
                city = _clean_string(row.get(column_map["city"])) if column_map.get("city") else ""
                external_id = _clean_string(row.get(column_map["external_id"])) if column_map.get("external_id") else None

                if not name or not province:
                    stats["skipped"] += 1
                    continue

                key = _compute_school_key(country, province.upper(), city, name)
                existing = session.exec(select(School).where(School.school_key == key)).first()

                if existing:
                    existing.city = city or existing.city
                    existing.updated_at = datetime.utcnow()
                    session.add(existing)
                    stats["updated"] += 1
                    continue

                new_school = School(
                    country=country,
                    province_state=province.upper(),
                    city=city or None,
                    school_name=name,
                    external_id=external_id or None,
                    source=source_label,
                    school_key=key
                )
                session.add(new_school)
                stats["inserted"] += 1
            except Exception as exc:
                stats["errors"] += 1
                print(f"Failed to import school row {stats['processed']}: {exc}")
        session.commit()

    return stats

def load_school_directory(session: Session):
    data_dir = Path(__file__).resolve().parents[1] / "data"
    import_run = SchoolImportRun(status="running")
    session.add(import_run)
    session.commit()

    us_path = data_dir / "schools_us.csv"
    ca_path = data_dir / "schools_ca.csv"

    try:
        us_stats = import_school_csv(session, us_path, "USA", "US_CSV", {
            "name": "School Name",
            "province": "State Abbr [Public School] Latest available year",
            "city": "Location City [Public School] 2023-24",
            "external_id": "School ID (12-digit) - NCES Assigned [Public School] Latest available year"
        })
        ca_stats = import_school_csv(session, ca_path, "Canada", "CA_CSV", {
            "name": "Facility_Name",
            "province": "Prov_Terr",
            "city": "City",
            "external_id": "Source_ID"
        })
        import_run.status = "completed"
        import_run.us_rows_processed = us_stats["processed"]
        import_run.ca_rows_processed = ca_stats["processed"]
        import_run.inserted_count = us_stats["inserted"] + ca_stats["inserted"]
        import_run.updated_count = us_stats["updated"] + ca_stats["updated"]
        import_run.skipped_count = us_stats["skipped"] + ca_stats["skipped"]
        import_run.error_count = us_stats["errors"] + ca_stats["errors"]
    except Exception as exc:
        import_run.status = "failed"
        import_run.errors_json = {"error": str(exc)}
        import_run.error_count = 1
    finally:
        import_run.finished_at = datetime.utcnow()
        session.add(import_run)
        session.commit()
if __name__ == "__main__":
    active_seed()
