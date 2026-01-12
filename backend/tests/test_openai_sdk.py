"""
Smoke test to verify OpenAI SDK supports Responses API.
"""
import pytest
from openai import AsyncOpenAI


class TestOpenAISDKCapabilities:
    """Test that the installed OpenAI SDK has required capabilities."""
    
    def test_responses_api_available(self):
        """Verify SDK has responses attribute for Responses API."""
        client = AsyncOpenAI(api_key="sk-test-dummy")
        assert hasattr(client, 'responses'), (
            "OpenAI SDK does not support Responses API. "
            "Upgrade to openai>=1.70.0"
        )
    
    def test_async_client_available(self):
        """Verify AsyncOpenAI is available."""
        try:
            client = AsyncOpenAI(api_key="sk-test-dummy")
            assert client is not None
        except ImportError as e:
            pytest.fail(f"AsyncOpenAI not available: {e}")
    
    @pytest.mark.asyncio
    async def test_json_schema_format_supported(self):
        """
        Verify that the SDK supports text.format with json_schema type.
        This is a structural test - we're checking the method signature exists.
        """
        client = AsyncOpenAI(api_key="sk-test-dummy")
        
        # Check responses.create exists
        assert hasattr(client.responses, 'create'), (
            "client.responses.create method not found"
        )
        
        # Note: We cannot actually call the API without valid credentials
        # This test only verifies the SDK structure is correct


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
