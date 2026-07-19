import os
import pytest
from fastapi.testclient import TestClient
from api.app import app

def test_rate_limiting():
    # Make multiple quick login attempts to trigger the 15-request rate limit
    os.environ["AISLEONE_ENV"] = "development"
    client = TestClient(app)
    responses = []
    
    try:
        # Send 20 requests in a row
        for _ in range(20):
            res = client.post(
                "/auth/token",
                json={"username": "malicious_user", "password": "wrong_password"}
            )
            responses.append(res)
            
        # Verify that at least some requests got a 429 Rate Limited response code
        status_codes = [r.status_code for r in responses]
        assert 429 in status_codes
        
        # Check the rate limit detail message
        limit_res = next(r for r in responses if r.status_code == 429)
        assert limit_res.json()["detail"] == "Too many login attempts. Please try again later."
    finally:
        os.environ["AISLEONE_ENV"] = "test"


def test_cors_middleware_headers():
    client = TestClient(app)
    # Check CORS options/origin header response
    res = client.options(
        "/auth/token",
        headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        }
    )
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "http://example.com"


def test_production_mode_key_enforcement():
    # Test that setting AISLEONE_ENV=production with default key throws a RuntimeError
    os.environ["AISLEONE_ENV"] = "production"
    os.environ["AISLEONE_SECRET_KEY"] = "aisleone-default-secret-key-development-only"
    
    # Reloading the auth module logic under production mode
    import sys
    import importlib
    
    if "api.auth" in sys.modules:
        # Re-importing should trigger the production validation check
        with pytest.raises(RuntimeError) as exc_info:
            importlib.reload(sys.modules["api.auth"])
        assert "CRITICAL SECURITY ERROR" in str(exc_info.value)
        
    # Reset env variables for development safety
    os.environ["AISLEONE_ENV"] = "development"
    os.environ["AISLEONE_SECRET_KEY"] = "b6cd3fde8a08152bc2a2fe928ba5f6d72861c8a14b518cfde04a29a1b1836109"
    importlib.reload(sys.modules["api.auth"])
