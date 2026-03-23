# ADR-005: React SPA + Vite (Next.js 제거)

- **Status**: Accepted
- **Date**: 2026-03-21
- **Deciders**: Project Lead

## Context

Next.js는 SSR/SSG가 핵심 가치이나, 본 프로젝트는:
- 내부 모니터링 도구 → SEO 불필요
- 온프레미스 배포 → Vercel 인프라 의존 불가
- 실시간 WebSocket 대시보드 → CSR이 더 적합
- FastAPI 백엔드에서 이미 API 제공 → BFF 불필요

## Decision

**React 18 + Vite SPA로 구성한다.**

- 라우팅: TanStack Router (타입 안전)
- 데이터: TanStack Query (서버 상태)
- 상태: Zustand (클라이언트 상태)
- 빌드: Vite (HMR, ESBuild)

## Consequences

### Positive
- 빌드 속도 극적 향상 (Vite vs Next.js)
- 배포 단순화 (정적 파일 → nginx/CDN)
- FastAPI와 명확한 역할 분리
- Next.js 버전 업그레이드 Breaking Changes 회피

### Negative
- `next/image` 최적화 없음 → 대시보드에 이미지 적으므로 영향 미미
- `next/link` 프리페치 없음 → TanStack Router 프리로드로 대체
- ISR/SSG 없음 → 모니터링 도구에 불필요

### Key Difference for AI Harness
- `import { useRouter } from 'next/router'` → 사용 금지
- `getServerSideProps`, `getStaticProps` → 존재하지 않음
- 파일 기반 라우팅 → TanStack Router 코드 기반 라우팅
