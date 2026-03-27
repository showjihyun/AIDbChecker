# Feature Spec: SSO/LDAP 연동

## 메타데이터
- **Spec ID**: FS-ADMIN-002
- **PRD 참조**: FR-ADMIN-002
- **우선순위**: P1 (Phase 2)
- **상태**: Approved
- **선행 Spec**: DM-001 (User 모델 — auth_provider 컬럼), MVP-ADMIN-001 (로컬 인증)
- **구현 파일**:
  - Backend: `backend/app/services/sso.py`, `backend/app/api/v1/auth.py` (확장)
  - Config: `backend/app/config.py` (SSO 설정 추가)
  - Test: `backend/tests/unit/test_admin_002_sso_spec.py`

---

## 1. 개요

기존 로컬 인증(email+password)에 추가로 **OIDC, LDAP, API Key** 인증을 지원합니다.
SAML 2.0은 Phase 3로 연기합니다 (라이브러리 복잡도, 금융/공공 고객 요구 시 추가).

### Phase 2 범위

| 인증 방식 | Phase | 설명 |
|----------|-------|------|
| **Local** (email+password) | MVP | 기존 유지 |
| **OIDC** (OpenID Connect) | Phase 2 | Google/Azure AD/Keycloak |
| **LDAP** (AD) | Phase 2 | Active Directory 바인드 |
| **API Key** | Phase 2 | 외부 시스템 M2M 인증 |
| SAML 2.0 | Phase 3 | 엔터프라이즈 SSO |

---

## 2. 설정

```python
# backend/app/config.py 추가 필드
# SSO / External Auth
SSO_ENABLED: bool = False
OIDC_ISSUER_URL: str = ""         # e.g., https://accounts.google.com
OIDC_CLIENT_ID: str = ""
OIDC_CLIENT_SECRET: str = ""
LDAP_SERVER_URL: str = ""         # e.g., ldap://ad.company.com:389
LDAP_BIND_DN: str = ""            # e.g., cn=admin,dc=company,dc=com
LDAP_BIND_PASSWORD: str = ""
LDAP_USER_SEARCH_BASE: str = ""   # e.g., ou=users,dc=company,dc=com
LDAP_USER_SEARCH_FILTER: str = "(uid={username})"
API_KEY_HEADER: str = "X-API-Key"
```

---

## 3. API Endpoints

### 3.1 OIDC 콜백
- **Method**: POST
- **Path**: `/api/v1/auth/oidc/callback`
- **Request**: `{ "id_token": "..." }` (프론트엔드에서 OIDC redirect 후 전달)
- **Response**: `TokenResponse` (기존 JWT access/refresh)

### 3.2 LDAP 로그인
- **Method**: POST
- **Path**: `/api/v1/auth/ldap`
- **Request**: `{ "username": "...", "password": "..." }`
- **Response**: `TokenResponse`

### 3.3 API Key 인증
- **Header**: `X-API-Key: {key}`
- 기존 `get_current_user` dependency에 API Key fallback 추가
- API Key는 `users` 테이블의 `preferences.api_key` JSONB에 저장

---

## 4. 인수 기준 (Acceptance Criteria)

- [ ] **AC-1**: config에 SSO_ENABLED, OIDC_*, LDAP_* 설정 추가
- [ ] **AC-2**: POST `/api/v1/auth/oidc/callback`으로 OIDC 토큰 → JWT 변환
- [ ] **AC-3**: POST `/api/v1/auth/ldap`로 LDAP 인증 → JWT 발급
- [ ] **AC-4**: X-API-Key 헤더로 인증 가능 (Bearer token 없이)
- [ ] **AC-5**: SSO 사용자 최초 로그인 시 `users` 테이블에 auto-provision (auth_provider 기록)
- [ ] **AC-6**: SSO_ENABLED=false 일 때 OIDC/LDAP 엔드포인트 비활성화 (404)

---

## 5. 의존성

- **선행 Spec**: DM-001 (User.auth_provider), MVP-ADMIN-001 (JWT 인프라)
- **연동 Spec**: AUDIT_LOG_SPEC (SSO 로그인 감사 기록)
