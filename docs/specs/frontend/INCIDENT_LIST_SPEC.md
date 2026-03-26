# Feature Spec: 인시던트 목록 페이지

## 메타데이터
- **Spec ID**: FS-DASH-004
- **PRD 참조**: FR-DASH-001, MVP-DASH-004
- **우선순위**: P1 (MVP)
- **상태**: Approved
- **선행 Spec**: DM-001 (incidents 테이블), API-001 (인시던트 API)
- **구현 파일**:
  - Backend: `backend/app/api/v1/incidents.py`
  - Frontend: `frontend/src/routes/pages/IncidentsPage.tsx`
  - Test: `backend/tests/unit/test_dash_004_spec.py`

---

## 1. 개요

활성 인시던트를 실시간으로 표시하는 페이지. severity 필터, 시간순 정렬, 상태 변경 기능 포함.

---

## 2. API 엔드포인트 (API_SPEC.md 참조)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/incidents` | 인시던트 목록 (severity, status 필터) |
| GET | `/api/v1/incidents/{id}` | 인시던트 상세 |
| PUT | `/api/v1/incidents/{id}/status` | 상태 변경 (acknowledge, resolve) |

### GET /api/v1/incidents Response

```json
{
  "items": [
    {
      "id": "uuid",
      "instance_id": "uuid",
      "instance_name": "pg-prod-01",
      "severity": "critical",
      "status": "open",
      "title": "CPU 사용률 95% (베이스라인: 40~60%)",
      "source": "ai_baseline",
      "detected_at": "2026-03-25T12:00:00Z",
      "acknowledged_at": null,
      "resolved_at": null
    }
  ],
  "total": 5
}
```

---

## 3. 프론트엔드 컴포넌트

### 3.1 IncidentsPage (`/incidents` 라우트 추가)

```
┌─────────────────────────────────────────────────────────┐
│ Incidents                                                │
│ Active incidents across all monitored instances          │
├─────────────────────────────────────────────────────────┤
│ [ALL] [CRITICAL] [WARNING] [NOTICE] [INFO]  ← 필터 탭   │
├─────────────────────────────────────────────────────────┤
│ 🔴 CRITICAL  pg-prod-01  CPU 95%        2분 전  [ACK]   │
│ 🟡 WARNING   pg-prod-02  Connections 85% 15분 전 [ACK]   │
│ 🟢 NOTICE    pg-staging  Vacuum 지연    1시간 전         │
│ ...                                                      │
├─────────────────────────────────────────────────────────┤
│ 인시던트가 없습니다 (EmptyState)                          │
└─────────────────────────────────────────────────────────┘
```

### 3.2 컴포넌트 구성

| 컴포넌트 | 위치 | 역할 |
|----------|------|------|
| `IncidentsPage` | `routes/pages/IncidentsPage.tsx` | 페이지 컨테이너 |
| `IncidentRow` | `components/incidents/IncidentRow.tsx` | 개별 인시던트 행 |
| `SeverityFilter` | `components/incidents/SeverityFilter.tsx` | severity 탭 필터 |

### 3.3 디자인 토큰

| severity | 색상 | 아이콘 |
|----------|------|--------|
| critical | `text-error` / `bg-error-container` | `error` |
| warning | `text-warning` / `bg-warning-container` | `warning` |
| notice | `text-tertiary` / `bg-tertiary-container` | `info` |
| info | `text-on-surface-variant` | `info` |

### 3.4 상태 변경

- `open` → `acknowledged`: ACK 버튼 클릭
- `acknowledged` → `resolved`: Resolve 버튼 클릭
- 상태 변경 시 PUT /api/v1/incidents/{id}/status 호출

---

## 4. 백엔드 API

### 4.1 인시던트 목록 API

```python
# backend/app/api/v1/incidents.py
# Spec: FS-DASH-004

@router.get("/incidents")
async def list_incidents(
    severity: str | None = None,  # critical, warning, notice, info
    status: str | None = None,    # open, acknowledged, resolved
    instance_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> IncidentListResponse: ...

@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: UUID, ...) -> IncidentResponse: ...

@router.put("/incidents/{incident_id}/status")
async def update_incident_status(
    incident_id: UUID,
    body: IncidentStatusUpdate,  # { status: "acknowledged" | "resolved" }
    session: AsyncSession = Depends(get_session),
) -> IncidentResponse: ...
```

---

## 5. WebSocket 이벤트

| Namespace | Event | Data |
|-----------|-------|------|
| `/ws/incidents` | `incident:new` | `{ id, severity, title, instance_name }` |
| `/ws/incidents` | `incident:update` | `{ id, status, resolved_at }` |

---

## 6. 라우터 등록

- TanStack Router에 `/incidents` 라우트 추가
- SideNav에 `report_problem Incidents` 네비게이션 항목 추가
- WebSocket `incident:new` 이벤트 시 Badge 카운터 표시

---

## 7. 인수 기준

- [ ] AC-1: GET /api/v1/incidents에서 severity/status 필터 동작
- [ ] AC-2: 인시던트 목록 페이지에서 severity별 색상 구분
- [ ] AC-3: ACK/Resolve 버튼으로 상태 변경 가능
- [ ] AC-4: 인시던트 없을 때 EmptyState 표시
- [ ] AC-5: WebSocket으로 신규 인시던트 실시간 수신
- [ ] AC-6: SideNav에 Incidents 메뉴 추가
