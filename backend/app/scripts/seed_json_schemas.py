
import logging
import sys
import os
import json

# Add backend directory to sys.path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from sqlmodel import Session, select
from app.database import engine
from app.models import JsonSchemaEntry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCHEMAS = [
    {
        "schema_id": "youask_plot_trigger_v1",
        "content": {
            "name": "plot_trigger_response",
            "schema": {
                "type": "object",
                "properties": {
                    "plot_needed": {
                        "type": "boolean",
                        "description": "Whether a plot is needed to answer the user's request."
                    },
                    "plot_type": {
                        "type": "string",
                        "enum": ["line", "scatter", "bar", "pie", "histogram", "none"],
                        "description": "The type of plot to generate."
                    },
                    "reason": {
                        "type": "string",
                        "description": "The reason why a plot is needed or not."
                    }
                },
                "required": ["plot_needed", "plot_type", "reason"],
                "additionalProperties": False
            },
            "strict": True
        }
    },
    {
        "schema_id": "youask_plot_spec_v1",
        "content": {
            "name": "plot_spec_response",
            "schema": {
                "type": "object",
                "properties": {
                    "plot_id": {
                        "type": "string",
                        "description": "A unique identifier for the plot."
                    },
                    "plotly_json": {
                        "type": "object",
                        "description": "The full Plotly JSON object representing the plot. Must include 'data' and 'layout'.",
                        "additionalProperties": True 
                    },
                    "attach_to_step_id": {
                        "type": "string",
                        "description": "The ID of the step in the solution plan to attach this plot to."
                    }
                },
                "required": ["plot_id", "plotly_json"],
                "additionalProperties": False
            },
            "strict": True
        }
    }
]

def seed_schemas():
    with Session(engine) as session:
        for schema_def in SCHEMAS:
            schema_id = schema_def["schema_id"]
            logger.info(f"Checking schema {schema_id}...")
            
            statement = select(JsonSchemaEntry).where(
                JsonSchemaEntry.schema_id == schema_id,
                JsonSchemaEntry.is_active == True
            )
            existing = session.exec(statement).first()

            if existing:
                logger.info(f"Updating existing schema {schema_id}")
                existing.content = schema_def["content"]
                existing.updated_by = "seed_script"
                session.add(existing)
            else:
                logger.info(f"Creating NEW schema {schema_id}")
                new_schema = JsonSchemaEntry(
                    schema_id=schema_id,
                    content=schema_def["content"],
                    updated_by="seed_script"
                )
                session.add(new_schema)
        
        session.commit()
        logger.info("Schema seeding complete.")

if __name__ == "__main__":
    seed_schemas()
