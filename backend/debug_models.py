from app.models import PromptTemplate
import pydantic

print(f"PromptTemplate fields: {PromptTemplate.__fields__.keys()}")
try:
    p = PromptTemplate(name="Test", slug="test")
    print("Success: PromptTemplate(name='Test', slug='test')")
except Exception as e:
    print(f"Error: {e}")
