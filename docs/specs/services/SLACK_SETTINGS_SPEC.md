# Feature Spec: Slack Integration Settings UI

## 메타데이터
- **Spec ID**: FS-ALERT-002
- **PRD 참조**: FR-ALERT-001, FR-ALERT-002
- **우선순위**: P0 (MVP)
- **상태**: Approved

---

## 1. 개요

Settings → Alert Channels 페이지에서 **Slack Bot Token + Channel ID**를 설정하고, 테스트 메시지를 발송할 수 있는 UI를 제공합니다.

---

## 2. API 엔드포인트

### 2.1 Slack 설정 조회
- **Method**: GET
- **Path**: `/api/v1/settings/slack`
- **Response**:
```python
class SlackSettingsResponse(BaseModel):
    has_bot_token: bool
    channel_id: str
    has_webhook_url: bool
```

### 2.2 Slack 설정 저장
- **Method**: PUT
- **Path**: `/api/v1/settings/slack`
- **Request**:
```python
class SlackSettingsUpdate(BaseModel):
    bot_token: str | None = None
    channel_id: str | None = None
    webhook_url: str | None = None
```

### 2.3 Slack 테스트 발송
- **Method**: POST
- **Path**: `/api/v1/settings/slack/test`
- **Response**: `{ success: bool, error: str }`

---

## 3. 인수 기준

- [ ] **AC-1**: GET `/settings/slack`에서 현재 설정 조회 (토큰은 마스킹)
- [ ] **AC-2**: PUT `/settings/slack`으로 Bot Token + Channel ID 저장 (DB 영구 저장)
- [ ] **AC-3**: POST `/settings/slack/test` 테스트 메시지 발송 성공/실패 반환
- [ ] **AC-4**: Settings → Alert Channels 페이지에 Slack 설정 폼 표시
