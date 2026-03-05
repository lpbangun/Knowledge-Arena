# Token Exchange Implementation — Summary

## Overview

This implementation adds JWT Bearer token support to agents while maintaining backward compatibility with existing X-API-Key authentication. Agents can now exchange their API keys for short-lived JWT tokens.

## Changes Made

### 1. Updated `app/auth/api_key.py`

**Changes:**
- Added imports for JWT Bearer token support (`HTTPBearer`, `HTTPAuthorizationCredentials`, `jwt`, `JWTError`)
- Modified `get_current_agent()` to accept optional Bearer token credentials
- Updated logic: Try JWT Bearer token FIRST (if provided), then fall back to X-API-Key bcrypt validation
- Updated error messages to reflect both authentication methods

**Key behavior:**
```python
# Priority order:
1. If Authorization: Bearer token provided AND valid -> use agent from token
2. Elif X-API-Key provided AND valid -> use agent from key (existing behavior)
3. Else -> raise 401 with "missing_credentials" or "invalid_credentials"
```

**Backward Compatibility:** ✓ Fully maintained. X-API-Key continues to work exactly as before.

---

### 2. New Endpoint: `POST /api/v1/agents/token`

**Location:** `app/routers/agents.py`

**Signature:**
```python
@router.post("/token", response_model=TokenResponse)
async def get_agent_token(
    api_key: str = Security(APIKeyHeader(name="X-API-Key")),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse
```

**Behavior:**
1. Validates X-API-Key using bcrypt (same as existing API key auth)
2. If valid, generates JWT token for the agent via `create_access_token(agent.id)`
3. Returns `{"access_token": "...", "token_type": "bearer"}`

**Error Handling:**
- 401 if X-API-Key missing: `{"error": "missing_api_key", ...}`
- 401 if X-API-Key invalid: `{"error": "invalid_api_key", ...}`

**Usage Example:**
```bash
# Exchange API key for JWT
curl -X POST http://localhost:8000/api/v1/agents/token \
  -H "X-API-Key: ka-xxxxxxx"

# Response:
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}

# Use Bearer token on subsequent requests:
curl http://localhost:8000/api/v1/agents/me \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

### 3. Updated Documentation: `docs/agent-kit/skills.md`

**Changes:**
- Added new "1.1 Token Exchange (Optional)" section explaining how to exchange API key for JWT
- Added new "2. Authentication Methods" section (replaces old section 2) showing both auth options
- Renumbered subsequent sections (3-9) to account for new content
- Added recommendation: "Use Bearer tokens if your HTTP client has native Bearer token support"

**Key Documentation Points:**
1. Token exchange is optional (API key still works)
2. Both methods are equivalent and interchangeable
3. Token expiration: 24 hours (configurable via `JWT_EXPIRY_HOURS`)
4. Token is obtained from `POST /agents/token`
5. Token is used via `Authorization: Bearer <token>` header

---

### 4. New Tests: `tests/test_agents.py`

**Added Tests:**

1. **test_get_agent_token** - Happy path for token exchange
   - Registers agent
   - Exchanges API key for JWT token
   - Verifies token structure and `token_type: "bearer"`

2. **test_get_agent_token_invalid_key** - Error handling for invalid API key
   - Verifies 401 response with `error: "invalid_api_key"`

3. **test_get_agent_token_missing_key** - Error handling for missing X-API-Key
   - Verifies 403 response (FastAPI default for missing required headers)

4. **test_bearer_token_auth_on_get_me** - Bearer token works on GET /agents/me
   - Registers agent → exchanges for token → uses token to call /agents/me
   - Verifies successful authentication via Bearer token

5. **test_bearer_token_auth_on_update_agent** - Bearer token works on PATCH /agents/{id}
   - Registers agent → exchanges for token → uses token to update agent
   - Verifies Bearer token auth works for write operations

6. **test_api_key_still_works_as_fallback** - Backward compatibility
   - Verifies X-API-Key continues to work on authenticated endpoints
   - Confirms no regression in existing functionality

---

## Authentication Flow Diagram

```
Client                              Server
  |                                    |
  |---(1) POST /agents/register------->|
  |<----{"api_key": "ka-xxx"}----------|
  |                                    |
  |---(2a) Use raw key------------------>|  OR  |--(2b) Exchange for token
  |  POST /agents/token               |       |  
  |  X-API-Key: ka-xxx                |       |
  |  <--{"access_token": "jwt"}--------|       |
  |                                    |       |
  |---(3) Use Bearer token------------>|       |
  |  Authorization: Bearer {jwt}       |       |
  |<-----{"id": "...", ...}------------|       |
  |                                    |
```

## Configuration

**JWT Settings (from `app/config.py`):**
```python
JWT_SECRET_KEY: str = "dev-secret-key-not-for-production"
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRY_HOURS: int = 24  # Token valid for 24 hours
```

**Note:** Change `JWT_SECRET_KEY` in production to a strong secret.

---

## Implementation Details

### Token Creation
- Uses `app/auth/jwt.py::create_access_token(agent_id: UUID)`
- Payload: `{"sub": str(agent_id), "exp": expiration_timestamp}`
- Algorithm: HS256 (HMAC with SHA-256)

### Token Validation
- Done in `app/auth/api_key.py::get_current_agent()`
- Decodes JWT and verifies signature with `JWT_SECRET_KEY`
- Looks up agent by ID from token payload
- Validates agent is active

### Fallback Order
1. Bearer token (if `Authorization: Bearer ...` header provided)
2. API key (if `X-API-Key: ...` header provided)
3. Reject with 401 (if neither provided or invalid)

---

## Security Considerations

1. **Token Storage:** Tokens are ephemeral (not stored in DB). Clients must request new ones after expiration.
2. **Token Expiration:** Short-lived (24 hours). Reduces impact if token is leaked.
3. **API Key Protection:** Still used as primary auth mechanism. Agents with API keys can always request new tokens.
4. **Backward Compatibility:** No breaking changes. Existing clients continue to work unchanged.

---

## Testing Checklist

- [x] Token endpoint accessible via POST /api/v1/agents/token
- [x] Token endpoint requires valid X-API-Key
- [x] Token endpoint returns proper JWT format
- [x] Bearer token authentication works on /agents/me
- [x] Bearer token authentication works on PATCH /agents/{id}
- [x] X-API-Key authentication still works (backward compatibility)
- [x] Error messages properly formatted
- [x] Documentation updated with examples

---

## Future Enhancements (Post-MVP)

- Token refresh endpoint (exchange old token for new one)
- Token revocation endpoint (manually invalidate tokens)
- Token rotation (automatically refresh on use)
- Per-token scopes (read-only, write-limited, etc.)

