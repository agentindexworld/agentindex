"""AgentIndex Passport System — RSA-signed, blockchain-chained agent identity"""

import hashlib
import json
import os
import secrets
import string
from datetime import datetime

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

KEYS_DIR = os.getenv("KEYS_DIR", "/app/keys")
PRIVATE_KEY_PATH = os.path.join(KEYS_DIR, "agentindex_private.pem")
PUBLIC_KEY_PATH = os.path.join(KEYS_DIR, "agentindex_public.pem")


def _load_private_key():
    with open(PRIVATE_KEY_PATH, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def _load_public_key():
    with open(PUBLIC_KEY_PATH, "rb") as f:
        return serialization.load_pem_public_key(f.read())


def get_public_key_pem() -> str:
    with open(PUBLIC_KEY_PATH, "r") as f:
        return f.read()


def generate_passport_id():
    chars = string.ascii_uppercase + string.digits
    unique_part = ''.join(secrets.choice(chars) for _ in range(6))
    return f"AIP-2026-{unique_part}"


def sign_passport(passport_data: dict) -> str:
    """Sign passport with RSA private key. Only AgentIndex can produce this."""
    private_key = _load_private_key()
    payload = json.dumps(passport_data, sort_keys=True, separators=(',', ':')).encode()
    signature = private_key.sign(payload, padding.PKCS1v15(), hashes.SHA256())
    return signature.hex()


def verify_passport_signature(passport_data: dict, signature_hex: str) -> bool:
    """Verify passport with RSA public key. Anyone can do this."""
    try:
        public_key = _load_public_key()
        payload = json.dumps(passport_data, sort_keys=True, separators=(',', ':')).encode()
        public_key.verify(bytes.fromhex(signature_hex), payload, padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False


def compute_chain_hash(passport_data: dict) -> str:
    """SHA256 hash of the full passport for chain linking."""
    payload = json.dumps(passport_data, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(payload).hexdigest()


def determine_passport_level(owner_email=None, owner_verified=False):
    if owner_verified and owner_email:
        return "verified"
    if owner_email:
        return "verified"
    return "standard"


def generate_referral_code(passport_id: str) -> str:
    parts = passport_id.split("-")
    if len(parts) >= 3:
        return f"REF-{parts[2]}"
    return f"REF-{secrets.token_hex(3).upper()}"


def build_passport_response(agent_data: dict) -> dict:
    passport_id = agent_data.get("passport_id", "")
    trust_score = float(agent_data.get("trust_score", 0))
    level = agent_data.get("passport_level", "standard")
    skills = agent_data.get("skills", [])
    if isinstance(skills, str):
        try:
            skills = json.loads(skills)
        except Exception:
            skills = []

    owner_email = agent_data.get("owner_email", "")
    masked = ""
    if owner_email and "@" in owner_email:
        local, domain = owner_email.split("@", 1)
        masked = f"{local[:2]}****@{domain}"

    base_api = f"https://{os.getenv('SERVER_HOST', 'localhost')}"

    return {
        "passport_id": passport_id,
        "sequence_number": agent_data.get("passport_sequence"),
        "previous_hash": agent_data.get("passport_previous_hash", ""),
        "chain_hash": agent_data.get("passport_chain_hash", ""),
        "holder": {
            "uuid": agent_data.get("uuid", ""),
            "name": agent_data.get("name", ""),
            "type": "autonomous-agent",
        },
        "owner": {
            "name": agent_data.get("owner_name", ""),
            "email": masked,
            "verified": bool(agent_data.get("owner_verified", False)),
            "country": agent_data.get("owner_country", ""),
        },
        "registry": {
            "name": "AgentIndex",
            "url": "https://agentindex.io",
            "authority": "AgentIndex Global Registry",
            "signature_algorithm": "RSA-2048-PKCS1v15-SHA256",
        },
        "trust_score": trust_score,
        "level": level,
        "skills": skills,
        "issued_at": agent_data.get("passport_issued_at", ""),
        "signature": agent_data.get("passport_signature", ""),
        "verification_url": f"{base_api}/api/passport/{passport_id}",
        "qr_code_url": f"{base_api}/api/passport/{passport_id}/qr",
        "badge_url": f"{base_api}/api/passport/{passport_id}/badge.svg",
        "public_key_url": f"{base_api}/api/passport/public-key",
    }
