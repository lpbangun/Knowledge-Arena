# Implementation Checklist — Token Exchange & Bearer Auth

## Requirement 1: Token Exchange Endpoint

### Requirement
> Does `app/routers/agents.py` have a `POST /api/v1/agents/token` endpoint that accepts X-API-Key and returns a JWT?

### Implementation
**Status:** ✓ COMPLETE

**File:** `app/routers/agents.py`
**Lines:** 67-106

**Endpoint Details:**
```
Method: POST
Path: /api/v1/agents/token
Authentication: X-API-Key header (required)
Response Model: TokenResponse
Response Code: 200 (success) or 401/403 (error)
```

**Request:**
```http
POST /api/v1/agents/token HTTP/1.1
X-API-Key: ka-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Success Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

---

## Requirement 2: Bearer Token Authentication Priority

### Requirement
> Does `app/auth/api_key.py` `get_current_agent` try JWT Bearer token FIRST before falling back to X-API-Key bcrypt?

### Implementation
**Status:** ✓ COMPLETE

**File:** `app/auth/api_key.py`
**Lines:** 28-60

**Authentication Logic (Priority Order):**
1. If Authorization: Bearer token provided AND valid → use agent from token
2. Elif X-API-Key provided AND valid → use agent from key
3. Else → raise 401 with appropriate error

**Verification:**
- ✓ Credentials parameter with HTTPBearer security scheme
- ✓ JWT decode with signature verification using JWT_SECRET_KEY
- ✓ Agent ID extracted from token payload `sub` field
- ✓ Fallback to X-API-Key if JWT unavailable or invalid
- ✓ Backward compatible: X-API-Key continues to work

---

## Requirement 3: Documentation of Token Exchange Flow

### Requirement
> Does `docs/agent-kit/skills.md` document the token exchange flow?

### Implementation
**Status:** ✓ COMPLETE

**File:** `docs/agent-kit/skills.md`

**Documentation Changes:**

**Section 1.1 — Token Exchange (Optional)** (Lines 37-63)
- Explains how to exchange API key for JWT token
- Shows curl example for token exchange
- Shows how to use Bearer token in requests
- Mentions token expiration (24 hours)
- Provides recommendation for when to use each method

**Section 2 — Authentication Methods** (Lines 76-91)
- Lists both authentication options side-by-side
- Explains equivalence of both methods
- States endpoint tries Bearer first, falls back to X-API-Key

---

## Requirement 4: Backward Compatibility

### Requirement
> Do NOT break existing X-API-Key auth — it must still work as a fallback

### Implementation
**Status:** ✓ COMPLETE & VERIFIED

**Verification Points:**

1. **Signature Unchanged**
   - ✓ get_current_agent still accepts api_key parameter
   - ✓ api_key_header security scheme still used
   - ✓ All existing dependencies work unchanged

2. **API Key Validation Unchanged**
   - ✓ Uses same get_key_prefix() function
   - ✓ Uses same bcrypt.checkpw() verification
   - ✓ Error messages updated to be generic but compatible

3. **Endpoint Behavior Unchanged**
   - ✓ All endpoints that use @Depends(get_current_agent) work with both auth methods
   - ✓ X-API-Key continues to work as fallback if no Bearer token provided
   - ✓ No endpoint signatures changed

4. **Test Coverage**
   - ✓ test_api_key_still_works_as_fallback verifies X-API-Key continues to work

---

## Requirement 5: New Tests

### Requirement
> Add a test in tests/ for the new endpoint and for Bearer token auth

### Implementation
**Status:** ✓ COMPLETE

**File:** `tests/test_agents.py`

**New Tests Added:**

1. **test_get_agent_token**
   - Tests happy path: register agent → exchange for token
   - Verifies response contains access_token and token_type: "bearer"

2. **test_get_agent_token_invalid_key**
   - Tests error handling for invalid API key
   - Verifies 401 response with error: "invalid_api_key"

3. **test_get_agent_token_missing_key**
   - Tests error handling for missing X-API-Key header
   - Verifies 403 response (FastAPI default)

4. **test_bearer_token_auth_on_get_me**
   - Tests Bearer token works for GET endpoint
   - Flow: register → get token → call /agents/me with Bearer

5. **test_bearer_token_auth_on_update_agent**
   - Tests Bearer token works for PATCH endpoint
   - Flow: register → get token → PATCH agent with Bearer

6. **test_api_key_still_works_as_fallback**
   - Tests backward compatibility
   - Verifies X-API-Key continues to work

---

## Requirement 6: Use Existing JWT Utilities

### Requirement
> Use existing jwt.py utilities where possible

### Implementation
**Status:** ✓ COMPLETE

**Utilities Used:**

1. **create_access_token() from app/auth/jwt.py**
   - Called in: get_agent_token() endpoint
   - Generates JWT token with agent ID as subject

2. **TokenResponse from app/schemas/auth.py**
   - Used as response model for token endpoint
   - Fields: access_token (str), token_type (str = "bearer")

3. **JWT Decode from python-jose**
   - Used in get_current_agent() for Bearer token validation
   - Reuses settings.JWT_SECRET_KEY and JWT_ALGORITHM

**No New Utilities Created:**
- ✓ Reused existing create_access_token()
- ✓ Reused existing TokenResponse schema
- ✓ Reused existing JWT settings from config

---

## Summary

All requirements implemented and verified:

- [x] POST /api/v1/agents/token endpoint created
- [x] Bearer token checked FIRST in get_current_agent()
- [x] X-API-Key fallback maintained (backward compatible)
- [x] Documentation updated with token exchange flow
- [x] 6 new comprehensive tests added
- [x] Existing JWT utilities leveraged
- [x] No breaking changes to existing code

**Total Files Modified:** 4
1. app/auth/api_key.py
2. app/routers/agents.py
3. docs/agent-kit/skills.md
4. tests/test_agents.py

**Total Tests Added:** 6
**Lines of Code Added:** ~200 (including tests and docs)
**Breaking Changes:** None
