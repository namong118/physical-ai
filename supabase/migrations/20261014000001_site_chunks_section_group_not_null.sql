-- 홈페이지 문서 챗봇: section·doc_group 을 필수 칸으로
-- 실행: python scripts/ingest_docs.py 로 모든 조각을 다시 넣고, 아래 "실행 전 확인"이 0 일 때만 실행
-- 넣기 스크립트가 항상 두 칸을 채우므로 이후 넣기에는 영향 없음.

-- 실행 전 확인 (0 이어야 함)
-- select count(*) from public.site_chunks where section is null or doc_group is null;

begin;

alter table public.site_chunks
  alter column section   set not null,
  alter column doc_group set not null;

commit;

-- 실행 후 확인 (두 행 모두 is_nullable 이 NO 이면 정상)
-- select column_name, is_nullable
--   from information_schema.columns
--  where table_schema = 'public' and table_name = 'site_chunks'
--    and column_name in ('section', 'doc_group')
--  order by column_name;
