# MEMORY.md

## 9차 개선 사이클 — 구현 계획 수립

### 상태: 계획 수립 완료, 구현 대기
### 일시: 2026-04-02

### 코드베이스 분석 완료 파일
- backend/simulation/social_rounds.py (1613줄) — 핵심 시뮬레이션 로직
- backend/simulation/social_runner.py (441줄) — 시뮬레이션 오케스트레이터
- backend/simulation/models.py (126줄) — Persona, SocialPost, PlatformState
- backend/simulation/persona_generator.py (445줄) — 페르소나 생성
- backend/simulation/platforms/base.py (210줄) — 플랫폼 추상 클래스
- backend/simulation/platforms/*.py — 5개 플랫폼 구현
- backend/simulation/graph_utils.py (219줄) — 그래프 빌딩/클러스터링
- backend/simulation/rate_limiter.py (252줄) — Redis RPM/TPM 리미터
- backend/tasks.py (769줄) — Celery 태스크
- backend/reporter.py (346줄) — 보고서 생성
- backend/context_builder.py (58줄) — 도메인 감지
- backend/llm.py (167줄) — LLM 래퍼
- backend/db.py — DB 스키마
- frontend/src/types.ts (217줄) — TypeScript 타입
- frontend/src/hooks/useSimulation.ts — SSE 스트림
- frontend/src/components/SimulationAnalytics.tsx — 차트
- frontend/src/components/ReportView.tsx — 리포트 뷰
- frontend/src/components/PersonaCardView.tsx — 페르소나 카드
- frontend/src/components/PlatformSimFeed.tsx — 피드 뷰
- frontend/src/pages/ResultPage.tsx — 결과 페이지

### 10차 구현 완료 (10개 항목)
- 항목 1: 중복 투표 방지 (voters 리스트, update_vote_counts에 voter_node_id)
- 항목 2: 자기 포스트 투표/리플라이 방지 (seed로 폴백)
- 항목 3: segment_distribution을 sentiment_timeline에 통합
- 항목 4: consensus_score 계산 추가
- 항목 5: attitude_shift trigger_summary 추가
- 항목 6: reply depth 제한 (최대 4단계)
- 항목 7: 피드에 에이전트 role/affiliation 노출
- 항목 8: 후반 라운드에서 seed 포스트 타겟 편중 완화
- 항목 9: response_rate 지표 추가
- 항목 10: seed 포스트를 감성 집계에서 제외

### 발견된 9차 개선 기회 (8개)
1. 페르소나 일관성 검증 (age/seniority 불일치 방지)
2. 세그먼트 분류 확장 ("other" 비율 감소)
3. 투표 가중치 기반 피드 랭킹
4. 라운드별 engagement 추세 분석
5. 크로스-플랫폼 페르소나 일관성 (동일 클러스터 → 일관 관점)
6. 리포트에 요약 통계 주입 (LLM에 명시적 수치 제공)
7. 시뮬레이션 완료 시간 추정 및 전송
8. Constructive sentiment을 segment별 breakdown에 반영

### Cycle 22 프론트엔드 개선 (2026-04-02)
- 아이템 2: HistoryItem에 adoption_score/max_agents 필드 추가, HistorySidebar/HistoryPage에 표시
- 아이템 3: DetailsView에 Network 탭 추가 (interaction_network 테이블 + echo_chamber_risk 표시), ResultPage에서 reportJson prop 전달
- 아이템 6: HistoryPage에 검색/verdict 필터 추가, HistorySidebar에 검색 입력 추가
