#!/usr/bin/env python3
"""
Tests for School Directory API Endpoints

Run with: pytest app/tests/test_school_directory.py -v
"""

import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestLocationEndpoints:
    """Tests for /locations/* endpoints."""
    
    def test_get_countries(self, client):
        """Test GET /api/v1/locations/countries."""
        response = client.get("/api/v1/locations/countries")
        assert response.status_code == 200
        data = response.json()
        assert "countries" in data
        assert "USA" in data["countries"]
        assert "Canada" in data["countries"]
    
    def test_get_provinces_usa(self, client):
        """Test GET /api/v1/locations/provinces for USA."""
        response = client.get("/api/v1/locations/provinces?country=USA")
        assert response.status_code == 200
        data = response.json()
        assert "provinces" in data
        assert "label" in data
        assert data["label"] == "State"
        assert "CA" in data["provinces"]  # California
        assert "TX" in data["provinces"]  # Texas
    
    def test_get_provinces_canada(self, client):
        """Test GET /api/v1/locations/provinces for Canada."""
        response = client.get("/api/v1/locations/provinces?country=Canada")
        assert response.status_code == 200
        data = response.json()
        assert "provinces" in data
        assert data["label"] == "Province/Territory"
        assert "ON" in data["provinces"]  # Ontario
        assert "BC" in data["provinces"]  # British Columbia
    
    def test_get_provinces_invalid_country(self, client):
        """Test GET /api/v1/locations/provinces with invalid country."""
        response = client.get("/api/v1/locations/provinces?country=Mexico")
        assert response.status_code == 400
    
    def test_get_grades(self, client):
        """Test GET /api/v1/locations/grades."""
        response = client.get("/api/v1/locations/grades")
        assert response.status_code == 200
        data = response.json()
        assert "grades" in data
        assert "Grade 4" in data["grades"]
        assert "Grade 12" in data["grades"]
        assert "College" in data["grades"]
        assert "University" in data["grades"]
        assert len(data["grades"]) == 11


class TestSchoolSearchEndpoints:
    """Tests for /schools/search endpoint."""
    
    def test_search_schools_no_query(self, client):
        """Test school search without query (lists all in province)."""
        response = client.get("/api/v1/schools/search?country=USA&province_state=CA")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_search_schools_with_query(self, client):
        """Test school search with query string."""
        response = client.get("/api/v1/schools/search?country=USA&province_state=CA&q=Lincoln")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # All results should contain "Lincoln" in the name
        for school in data:
            assert "Lincoln" in school["school_name"].lower() or "lincoln" in school["school_name"].lower()
    
    def test_search_schools_invalid_country(self, client):
        """Test school search with invalid country."""
        response = client.get("/api/v1/schools/search?country=Mexico&province_state=XX")
        assert response.status_code == 400
    
    def test_search_schools_invalid_province(self, client):
        """Test school search with invalid province for country."""
        response = client.get("/api/v1/schools/search?country=USA&province_state=ON")  # ON is Canada
        assert response.status_code == 400
    
    def test_search_schools_limit(self, client):
        """Test school search respects limit parameter."""
        response = client.get("/api/v1/schools/search?country=USA&province_state=CA&limit=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 5


class TestProfileLocationEndpoint:
    """Tests for PATCH /user/profile-location endpoint."""
    
    def test_update_profile_location_success(self, client, test_user_id):
        """Test successful profile location update."""
        response = client.patch(
            f"/api/v1/user/profile-location?user_id={test_user_id}",
            json={
                "profile_country": "Canada",
                "profile_province_state": "ON",
                "grade_level": "Grade 9"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["profile_country"] == "Canada"
        assert data["profile_province_state"] == "ON"
        assert data["grade_level"] == "Grade 9"
    
    def test_update_profile_location_invalid_country(self, client, test_user_id):
        """Test profile update with invalid country."""
        response = client.patch(
            f"/api/v1/user/profile-location?user_id={test_user_id}",
            json={
                "profile_country": "Mexico",
                "profile_province_state": "XX",
                "grade_level": "Grade 9"
            }
        )
        assert response.status_code == 400
    
    def test_update_profile_location_invalid_province(self, client, test_user_id):
        """Test profile update with invalid province for country."""
        response = client.patch(
            f"/api/v1/user/profile-location?user_id={test_user_id}",
            json={
                "profile_country": "USA",
                "profile_province_state": "ON",  # ON is Canada, not USA
                "grade_level": "Grade 9"
            }
        )
        assert response.status_code == 400
    
    def test_update_profile_location_invalid_grade(self, client, test_user_id):
        """Test profile update with invalid grade level."""
        response = client.patch(
            f"/api/v1/user/profile-location?user_id={test_user_id}",
            json={
                "profile_country": "Canada",
                "profile_province_state": "ON",
                "grade_level": "Grade 13"  # Invalid
            }
        )
        assert response.status_code == 400


# Fixtures
@pytest.fixture
def client():
    """Create a test client."""
    from fastapi.testclient import TestClient
    from app.main import app  # Adjust import based on your app structure
    return TestClient(app)


@pytest.fixture
def test_user_id(client):
    """Get or create a test user ID."""
    # In a real test, you'd create a test user
    # For now, return a placeholder
    return 1
