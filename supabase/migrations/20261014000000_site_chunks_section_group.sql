-- 홈페이지 문서 챗봇: 조각 가독성 — 섹션 제목과 문서 분야 칸 추가
-- 실행: 대시보드 SQL Editor 에서 이 파일 전문을 한 번에 실행 (챗봇용 프로젝트인지 먼저 확인)
-- 순서: 이 파일 실행 → 칸 확인 → python scripts/ingest_docs.py (모든 조각 다시 넣기)
--       → 20261014000001_site_chunks_section_group_not_null.sql
-- 기존 heading(제목 경로)은 출처 링크에 쓰므로 바꾸지 않음. 넣기 전 기존 행은 두 칸이 비어 있음.

begin;

alter table public.site_chunks
  add column section   text,   -- 조각이 속한 마지막 제목 (예: "4. 기술 스택 (Technology Stack)", "연결 요약")
  add column doc_group text;   -- docs.json 의 group (제품 / 설계·검증 / 실습), 홈페이지는 '홈페이지'

comment on column public.site_chunks.section   is '조각이 속한 마지막 제목. heading(제목 경로)은 출처 링크용으로 그대로 둠';
comment on column public.site_chunks.doc_group is 'docs.json 의 group (제품 / 설계·검증 / 실습), 홈페이지는 홈페이지';

commit;

-- 실행 후 확인 (두 행이 나오고 is_nullable 이 YES 이면 정상)
-- select column_name, data_type, is_nullable
--   from information_schema.columns
--  where table_schema = 'public' and table_name = 'site_chunks'
--    and column_name in ('section', 'doc_group')
--  order by column_name;
