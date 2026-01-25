from sqlmodel import Session, select
from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv() 

from app.database import engine
from app.models import SystemConfig, PromptAsset, PlanPromptLink, Plan

def generate_markdown():
    with Session(engine) as session:
        output = "# Database Configuration Values\n\n"
        
        # 1. SystemConfig
        output += "## 1. Table: systemconfig\n"
        output += "| KEY | VALUE | DESCRIPTION |\n"
        output += "| :--- | :--- | :--- |\n"
        rows = session.exec(select(SystemConfig).order_by(SystemConfig.key)).all()
        for r in rows:
            output += f"| {r.key} | {r.value} | {r.description or ''} |\n"
        
        # 2. PromptAsset
        output += "\n## 2. Table: promptasset\n"
        output += "| ID | KEY | KIND | PATH |\n"
        output += "| :--- | :--- | :--- | :--- |\n"
        rows = session.exec(select(PromptAsset).order_by(PromptAsset.id)).all()
        for r in rows:
            output += f"| {r.id} | {r.key} | {r.kind} | {r.path} |\n"

        # 3. Plan
        output += "\n## 3. Table: plan\n"
        output += "| ID | NAME | SLUG | FEATURES |\n"
        output += "| :--- | :--- | :--- | :--- |\n"
        rows = session.exec(select(Plan).order_by(Plan.id)).all()
        for r in rows:
            output += f"| {r.id} | {r.name} | {r.slug} | {r.features} |\n"

        # 4. PlanPromptLink
        output += "\n## 4. Table: planpromptlink\n"
        output += "| ID | PLAN_ID | MODE | SYS_ID | SCH_ID |\n"
        output += "| :--- | :--- | :--- | :--- | :--- |\n"
        rows = session.exec(select(PlanPromptLink).order_by(PlanPromptLink.id)).all()
        for r in rows:
            output += f"| {r.id} | {r.plan_id} | {r.mode} | {r.system_prompt_asset_id} | {r.schema_prompt_asset_id} |\n"
            
        with open("config_report.md", "w", encoding="utf-8") as f:
            f.write(output)
        print("config_report.md generated.")

if __name__ == "__main__":
    generate_markdown()
