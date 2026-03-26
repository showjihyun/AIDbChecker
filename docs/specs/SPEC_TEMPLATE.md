# Feature Spec: {제목}

## 메타데이터
- **Spec ID**: FS-{MODULE}-{NNN}
- **PRD 참조**: FR-{CATEGORY}-{NNN}
- **우선순위**: P0 (MVP) | P1 | P2 | P3
- **상태**: Draft | Approved | Implemented
- **선행 Spec**: {comma-separated Spec IDs or "없음"}
- **구현 파일**:
  - Backend: `backend/app/api/v1/{module}.py`, `backend/app/services/{module}.py`
  - Frontend: `frontend/src/components/{module}/{Component}.tsx`
  - Test: `backend/tests/unit/test_{module}.py`

---

## 1. 개요
{1-2 문장: 이 Spec이 무엇을 하는지}

---

## 2. 인터페이스 계약

### 2.1 API 엔드포인트
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| {GET/POST/PUT/DELETE} | {path} | {role} | {description} |

### 2.2 Request/Response 스키마
```python
class {Name}Request(BaseModel):
    {field}: {type}

class {Name}Response(BaseModel):
    {field}: {type}
```

### 2.3 프론트엔드 컴포넌트 (해당 시)
| Component | Props | 역할 |
|-----------|-------|------|
| {Name} | {props} | {description} |

---

## 3. 동작 규격
{핵심 로직, 알고리즘, 상태 전이, 에러 처리 등}

---

## 4. 인수 기준

- [ ] AC-1: {검증 가능한 한 문장}
- [ ] AC-2: {검증 가능한 한 문장}

---

## 5. 의존성
- **선행**: {Spec IDs}
- **사용**: {어떤 Spec이 이 Spec을 참조하는지}
