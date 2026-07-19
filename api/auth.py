import hmac
import hashlib
import base64
import json
import time
import os
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from utils.db_helpers import get_conn

def load_dotenv():
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                if key not in os.environ:
                    os.environ[key] = val.strip()

# Parse env config on start
load_dotenv()

ENV = os.environ.get("AISLEONE_ENV", "development").lower()
SECRET_KEY = os.environ.get("AISLEONE_SECRET_KEY", "aisleone-default-secret-key-development-only")

if ENV == "production":
    if SECRET_KEY in [
        "aisleone-default-secret-key-development-only",
        "aisleone-super-secret-key-change-in-production",
        "",
        None
    ]:
        raise RuntimeError("CRITICAL SECURITY ERROR: Default or empty secret key configured in production environment!")

security = HTTPBearer()

def base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

def base64url_decode(data: str) -> bytes:
    padding = '=' * (4 - (len(data) % 4))
    return base64.urlsafe_b64decode(data + padding)

def hash_password(password: str) -> str:
    """Hash password using SHA256 and a simple static salt."""
    salt = "aisleone-salt-2026"
    hashed = hashlib.sha256((password + salt).encode('utf-8')).hexdigest()
    return hashed

def verify_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash

def create_token(payload: Dict[str, Any], expires_in: int = 86400) -> str:
    """Create a signed JWS token for the user session."""
    token_payload = payload.copy()
    token_payload["exp"] = int(time.time()) + expires_in
    
    payload_bytes = json.dumps(token_payload).encode('utf-8')
    payload_b64 = base64url_encode(payload_bytes)
    
    # Calculate HMAC signature
    sig = hmac.new(SECRET_KEY.encode('utf-8'), payload_b64.encode('utf-8'), hashlib.sha256).digest()
    sig_b64 = base64url_encode(sig)
    
    return f"{payload_b64}.{sig_b64}"

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify the signature and expiration of a token."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
            
        payload_b64, sig_b64 = parts
        
        # Verify signature
        expected_sig = hmac.new(SECRET_KEY.encode('utf-8'), payload_b64.encode('utf-8'), hashlib.sha256).digest()
        expected_sig_b64 = base64url_encode(expected_sig)
        
        if not hmac.compare_digest(sig_b64, expected_sig_b64):
            return None
            
        # Decode payload
        payload_bytes = base64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode('utf-8'))
        
        # Check expiration
        if payload.get("exp", 0) < time.time():
            return None
            
        return payload
    except Exception:
        return None

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Dependency injection wrapper to parse and query active user tier and memberships."""
    token = credentials.credentials
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    username = payload.get("username")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, username, tier, club_memberships, zip_code FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User session invalid - user not found",
        )
        
    user_data = dict(row)
    # Parse club memberships from JSON text
    try:
        user_data["club_memberships"] = json.loads(user_data["club_memberships"])
    except Exception:
        user_data["club_memberships"] = []
        
    return user_data
