# HANDOFF — 새 세션 인수인계

> 기준일 2026-10-14. 작업을 마칠 때 "현재 상태"와 "남은 일"을 갱신합니다.

## 1. 프로젝트와 레포 역할
- **별일없지:** 혼자 사시는 부모님 댁의 Edge AI 카메라·생활센서가 생활 리듬을 읽고, 가족에게는 영상 대신 생활 신호만 보내는 생활안심 시스템.
- **이 레포:** 소개 홈페이지(GitHub Pages, `main` push 시 곧 공개)와 PRD·설계 문서. 예외로 챗봇용 `scripts/`, `supabase/`만 코드를 둠.
- **개발 코드:** 별도 레포 [namong118/Byeolileopji](https://github.com/namong118/Byeolileopji) (앱, Cloudflare Worker, ESP32 펌웨어). 이 레포에서는 개발하지 않음.

## 2. 현재 상태

**홈페이지 `index.html` 섹션 (위→아래):** 히어로(`#top`) → 왜 필요한가 `#problem` → Quiet Care Principles → 작동 방식 `#how` → 전처리·후처리 `#pipeline` → 공간별 설치 `#spaces` → 하루 시나리오 `#day` → Sensor vs. Physical AI → 프라이버시 `#privacy` → 성공 지표 `#metrics` → 기술 스택 `#tech` → 범위·로드맵 `#poc` → 도입 효과 `#roi` → 문서 `#docs` → 마무리 CTA. 오른쪽 아래에 챗봇 창.

**`docs.json` 문서 목록** (그룹: 제품 / 설계·검증 / 실습, "실습"은 별도 블록)

| id | 파일 | 버전 · 날짜 | 상태 |
|---|---|---|---|
| prd | `PRD/PRD.md` (+ `PRD_v1.2.docx`) | v1.2 · 2026-10-07 | 확정 |
| vision-preprocessing-design | `report/vision-preprocessing-design.md` | v1.1 · 2026-10-07 | 진행 중 |
| model-training-validation | `report/model-training-validation.md` | v1.1 · 2026-10-12 | 계획 |
| hardware-parts | `report/hardware-parts.md` (+ `images/hardware/` 개념도·상세 배선도) | v1.1 · 2026-10-14 | 진행 중 |
| vision-models-practice | `report/vision-models-practice.md` | v1.0 · 2026-10-12 | 확정 |

**챗봇 구성**

| 항목 | 값 |
|---|---|
| Supabase 프로젝트 ref | `zerclhuaekfsseriyevp` (챗봇용 실습 프로젝트 하나만, MCP는 `read_only=true`) |
| 테이블 (`public`, RLS 켬, 정책 없음) | `site_documents`, `site_chunks`, `site_rate_events` |
| RPC | `site_match_chunks(query_embedding, match_count, min_similarity)`, `site_check_rate(p_ip_hash, p_per_minute, p_per_day, p_global_per_day)` |
| 마이그레이션 | `supabase/migrations/20261013000000_site_chat.sql` |
| Edge Function | `site-chat` (`supabase/functions/site-chat/index.ts`, `verify_jwt = false`) |
| 임베딩 | `gemini-embedding-2`, 768차원 — `supabase/functions/_shared/embedding.json` (넣기 스크립트와 함께 씀) |
| 생성 모델 | `gemini-3.5-flash-lite` — `index.ts`의 `GEN_MODEL` 상수, temperature 0 |
| 요청 상한 | IP당 1분 5회 · 24시간 30회(`PER_DAY`), 전체 24시간 300회 (1분·전체는 SQL 기본값) |
| 검색 | `MATCH_COUNT` 5, `MIN_SIMILARITY` 0.5 (0.5 유지로 결정, 문서 밖 판단은 생성 단계 고정 문구에 맡김) |
| 응답 status | `ok`, `no_match`, `limited`, `unavailable`, `invalid` (+ `{mode:"status"}`은 남은 횟수 `remaining`·`limit`·`next_at`만) |
| 허용 Origin | `https://namong118.github.io`, `http://localhost:8000` |
| 넣은 조각 | 문서 5개 + 홈페이지 = 99개 (hardware-parts v1.1 넣기 전. dry-run 기준 넣은 뒤 103개) |

**secret 이름** (값은 어디에도 쓰지 않음)
- Edge Function: `GEMINI_API_KEY`, `RATE_SALT` (사용자가 대시보드에서 설정), `SUPABASE_URL`·`SUPABASE_SECRET_KEYS`·`SUPABASE_PUBLISHABLE_KEYS` (기본 제공)
- 로컬 `.env` (커밋 안 함, 이름은 `.env.example`): `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `GEMINI_API_KEY`
- 홈페이지에는 공개용 publishable 키만 둠.

## 3. 자주 하는 작업

**문서 추가·수정**
1. 문서 수정 → 첫머리 버전·날짜와 `docs.json`의 `version`·`date`를 같게
2. 새 문서면 `docs.json`의 `docs`에 기존 항목과 같은 형식으로 추가
3. 조각 확인: `python scripts/ingest_docs.py --dry-run` (미리보기는 `--dry-run --show 3`)
4. 넣기 — **사용자 실행**: `python scripts/ingest_docs.py` (바뀐 문서만, 전체 다시 넣기는 `--force`)
5. 넣은 뒤 MCP 읽기 조회로 조각 수·임베딩 확인

**site-chat 배포** (명령 전문을 먼저 보고하고 승인 후 실행)
```
npx supabase functions deploy site-chat --project-ref zerclhuaekfsseriyevp --use-api
```
DB 쓰기(테이블·데이터 변경)는 SQL 전문을 작성해 사용자가 대시보드 SQL Editor에서 실행.

**로컬 확인**
```
python -m http.server 8000
```
- Chrome에서 `http://localhost:8000/` 확인 (챗봇은 이 Origin만 허용)
- 폭 1440 · 1024 · 375px(375는 기기 에뮬레이션), 가로 스크롤 없음, 콘솔 오류 없음(Tailwind CDN 경고는 기존과 같음)
- 문서는 `doc.html?file=report/….md`에서 목차·표·이미지 확인. 한 줄에 `~`가 두 개면 취소선이 되므로 `–` 사용

## 4. 남은 일
- **비전 실측:** 시나리오 녹화 → 라벨링 → 사전학습 모델 기준선 측정 → 파인튜닝 여부 결정 (모델 계획 문서 순서)
- **비전 비교:** 실제 영상으로 단계별 on/off 비교, Raspberry Pi FPS 측정 → 홈페이지 "실측 전" 항목과 문서 결과표에 반영
- **비전 비교:** YOLO + MediaPipe vs YOLO-pose 단독, 같은 영상으로 정확도·FPS 비교
- **비전 코드:** 사람 선택을 ByteTrack(Supervision)으로 교체
- **보조 모델 검토 (직접 촬영 영상):** YOLOE로 Zone 초안, SigLIP으로 약점 장면 검색, SAM 3로 라벨 초안
- **하드웨어:** 확인 필요로 남긴 전류(Pi 5 추론 부하, Active Cooler, Camera Module 3, ESP32-S3 보드 전체), 웹캠·IR LED 제품 선정, ESP32 대수(위치당/센서당) 결정, MC-38 GPIO5 배선·펌웨어
- **하드웨어 v1.1 넣기:** `python scripts/ingest_docs.py` 실행 후 조각 수 확인 (사용자 실행)
- **개념도:** 부품이 바뀌면 `images/hardware/parts-overview.webp` 다시 만들기 — 기준은 문서와 상세 배선도
- **연결 요약 표 검토:** 1~4장과 다른 표기(IR LED 제어 방법, Pi → Cloudflare Worker)
- **안전 검토 (기획 단계):** 최악의 경우, 힘·속도·무게 최소화, 안전한 상태 정의, 예상 밖의 사용자, 대책 순서(없앤다 → 막는다 → 알린다) — 검토 예정
- **챗봇:** 응답에서 `top_similarity` 빼기(아직 응답에 있음)
- **챗봇 지시:** 절감액 답의 "가정" 표시 보완(보류 중), "알림은 얼마나 빨리 오나요?" 답에서 "아직 측정 전"이 빠지는 문제
- **챗봇:** `gemini-3.5-flash-lite` 무료 한도 수치 확인 (AI Studio)
- **홈페이지:** 히어로 배지 "영상 외부 전송 0건"이 측정값처럼 읽힐 수 있음 — 문구 검토
- **확인:** 배포 주소에서 메뉴·문서 모음·뷰어 직접 확인, 768~1023px 구간, 실제 노트북 배율(125%·150%)과 실제 휴대폰
- **정리 결정:** 미추적 파일 `code/`(`byeol_edge_vision (1).zip`), `report/checklist.md`, `report/preprocess.md`

## 5. 새 세션 시작 방법
1. `CLAUDE.md`(작업 규칙)와 이 파일을 먼저 읽습니다.
2. `report/devlog.md`는 필요할 때 **맨 위(최신) 항목만** 읽습니다.
3. 작업을 마치면 개발일지 해당 날짜 항목과 이 파일의 "현재 상태"·"남은 일"을 갱신합니다.
