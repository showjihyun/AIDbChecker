# NeuralDB v1.3.0 프로젝트 회고

> 기간: 2026-03-25 ~ 2026-04-02 (8일)

---

## 메트릭

| 지표 | 값 |
|------|-----|
| 총 커밋 | 264 |
| Merged PRs | 81 |
| Backend Python LOC | 21,467 |
| Frontend TS/TSX LOC | 9,068 |
| Test LOC | 13,867 |
| Spec 문서 | 53개 |
| ACs | 285/288 (99%) |
| Tests | 584 passed, 0 failed |
| 릴리스 | v1.0.0 → v1.2.0 → v1.3.0 |

---

## 주요 성과

### Sprint 1 (Day 1-4): MVP Foundation → v1.0.0
- 프로젝트 초기화 → Docker Compose → 전체 스키마
- Auth/RBAC, Instance CRUD, 메트릭 수집, ASH, 베이스라인
- React 대시보드, KPI, NL2SQL, DBA Agent 기본

### Sprint 2 (Day 4-5): DBA Agent + Security → v1.0.2
- SafetyGuard 4-Level, ExecutionEngine, MCP Protocol
- 19개 보안 취약점 발견 + 수정

### Sprint 3 (Day 5-6): Proactive + Tier 2 → v1.1.0
- Proactive Agent (Quick Check + Deep Analysis + Morning Report)
- Knowledge Graph Auto-Refresh, Self-Healing

### Sprint 4 (Day 6-8): Quality + Reports + Claude → v1.3.0
- DBA Agent 답변 품질: ReAct → **Claude Native Tool Use**
- Multi-Turn Memory (Valkey 구조화 세션)
- DBA Report (Daily/Weekly/Monthly) + PDF + Slack
- E2E 테스트, 운영 가이드

---

## 핵심 기술 결정

| 결정 | 근거 | 결과 |
|------|------|------|
| Claude Native Tool Use | ReAct 텍스트 파싱의 한국어 품질 한계 | 3,700자+ 마크다운 분석, SQL 포함 |
| Valkey 구조화 세션 | 단순 텍스트 5턴 → Entity 추출 + 10턴 | "그 테이블" 대명사 해소 |
| fpdf2 + NotoSansKR | weasyprint 시스템 의존성 회피 | Docker에서 한국어 PDF 정상 |
| system_settings 테이블 | 환경변수 메모리 초기화 문제 | Docker 재시작 후에도 설정 유지 |

---

## 교훈

### 잘된 것
- **Spec-Driven**: SPEC 먼저 → AC 정의 → 테스트 스텁 → 구현. 빠짐 없이 체계적
- **4-Pillar Pre-Commit**: lint → type → test → AC 대시보드. 품질 자동 보장
- **Claude Native Tool Use**: ReAct 대비 압도적 품질 향상. DBA 실무에 바로 활용 가능
- **병렬 개발**: 2개 Claude Code 에이전트 동시 운영 → 충돌 관리 경험

### 개선할 것
- **Docker port mapping 혼동** (8000 vs 8001) → 문서 명확화 필요
- **bcrypt 5.x 호환**: passlib → bcrypt import 순서 이슈에 시간 소요
- **ReAct 누수**: LLM이 "Final Answer:" 미출력 시 내부 추론 노출 → Native Tool Use로 근본 해결
- **SPEC-first 위반 1회**: 코드 먼저 구현 후 SPEC 추가 → 피드백 반영하여 이후 준수

---

## v1.3.0 릴리스 요약

```
v1.0.0  MVP 기반 (49 PRs, 89.5K LOC)
v1.0.2  DBA Agent + Security (16 PRs)
v1.1.0  Proactive Agent (8 PRs)
v1.2.0  Persistent Settings + Spec 100%
v1.3.0  Claude Native Tool Use + Reports + Multi-Turn (81 PRs total)
```
