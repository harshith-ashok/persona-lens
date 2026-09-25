#!/usr/bin/env bash
# Generates a .env with a fresh JWT secret and matching anon/service_role keys.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && { echo ".env already exists; delete it to regenerate"; exit 1; }
python3 - <<'PY' > .env
import base64, hmac, hashlib, json, secrets
def b64(b): return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
secret = secrets.token_hex(32)
def jwt(role):
    h = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    p = b64(json.dumps({"role": role, "iss": "supabase-local", "iat": 1700000000, "exp": 2400000000}).encode())
    s = b64(hmac.new(secret.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest())
    return f"{h}.{p}.{s}"
print(f"POSTGRES_PASSWORD={secrets.token_hex(16)}")
print(f"JWT_SECRET={secret}")
print(f"ANON_KEY={jwt('anon')}")
print(f"SERVICE_ROLE_KEY={jwt('service_role')}")
print("API_EXTERNAL_URL=http://localhost:8000")
print("SITE_URL=http://localhost:5173")
PY
echo "Wrote .env"
