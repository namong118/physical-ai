-- 홈페이지 문서 챗봇: 문서·조각·요청 기록 테이블과 RPC
-- 실행: 대시보드 SQL Editor 에서 이 파일 전문을 한 번에 실행 (챗봇용 프로젝트인지 먼저 확인)

begin;

-- 문서: docs.json 항목 1개 = 1행
create table public.site_documents (
  id           text primary key,                 -- docs.json 의 id
  title        text not null,
  file         text not null unique,             -- 예: report/model-training-validation.md
  version      text,
  doc_date     date,
  content_hash text not null,                    -- 바뀐 문서만 다시 넣기 위한 값
  updated_at   timestamptz not null default now()
);

-- 조각: 문서 조각 + 임베딩
create table public.site_chunks (
  id          bigint generated always as identity primary key,
  document_id text not null references public.site_documents(id) on delete cascade,
  chunk_index integer not null,
  heading     text,                              -- 조각이 속한 제목 경로
  content     text not null,
  embedding   extensions.vector(768) not null,
  unique (document_id, chunk_index)
);

create index site_chunks_embedding_idx
  on public.site_chunks using hnsw (embedding extensions.vector_cosine_ops);

-- 요청 기록: 솔트 해시와 시각만 (질문 내용·원문 IP 없음)
create table public.site_rate_events (
  id         bigint generated always as identity primary key,
  ip_hash    text not null check (ip_hash ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now()
);

create index site_rate_events_ip_time_idx on public.site_rate_events (ip_hash, created_at);
create index site_rate_events_time_idx    on public.site_rate_events (created_at);

-- RLS 켜고 정책 없음 + 브라우저 역할 권한 회수
alter table public.site_documents   enable row level security;
alter table public.site_chunks      enable row level security;
alter table public.site_rate_events enable row level security;
revoke all on public.site_documents, public.site_chunks, public.site_rate_events
  from anon, authenticated;

-- 검색 RPC
create function public.site_match_chunks(
  query_embedding extensions.vector(768),
  match_count     integer          default 5,
  min_similarity  double precision default 0.5
)
returns table (
  document_id text, title text, file text,
  heading text, content text, similarity double precision
)
language sql
stable
security invoker
set search_path = ''
as $$
  select c.document_id, d.title, d.file, c.heading, c.content,
         1 - (c.embedding operator(extensions.<=>) query_embedding) as similarity
  from public.site_chunks c
  join public.site_documents d on d.id = c.document_id
  where 1 - (c.embedding operator(extensions.<=>) query_embedding) >= min_similarity
  order by c.embedding operator(extensions.<=>) query_embedding
  limit least(greatest(match_count, 1), 10);
$$;

-- 횟수 확인 + 기록 RPC (통과한 요청만 기록, 1일 지난 기록은 호출 때마다 정리)
create function public.site_check_rate(
  p_ip_hash        text,
  p_per_minute     integer default 5,
  p_per_day        integer default 30,
  p_global_per_day integer default 300
)
returns table (allowed boolean, reason text)
language plpgsql
volatile
security invoker
set search_path = ''
as $$
declare
  v_minute integer;
  v_day    integer;
  v_global integer;
begin
  if p_ip_hash is null or p_ip_hash !~ '^[0-9a-f]{64}$' then
    raise exception 'invalid ip hash';
  end if;

  -- 동시 요청이 상한을 넘지 않도록 한 번에 하나씩
  perform pg_advisory_xact_lock(hashtext('site_check_rate'));

  -- 1일 지난 기록 정리
  delete from public.site_rate_events where created_at < now() - interval '1 day';

  select count(*) into v_global from public.site_rate_events;
  select count(*) filter (where created_at >= now() - interval '1 minute'), count(*)
    into v_minute, v_day
    from public.site_rate_events
   where ip_hash = p_ip_hash;

  if v_global >= p_global_per_day then
    return query select false, 'global_daily'; return;
  end if;
  if v_day >= p_per_day then
    return query select false, 'ip_daily'; return;
  end if;
  if v_minute >= p_per_minute then
    return query select false, 'ip_minute'; return;
  end if;

  insert into public.site_rate_events (ip_hash) values (p_ip_hash);
  return query select true, null::text;
end;
$$;

-- RPC 실행 권한: service_role 만
revoke execute on function public.site_match_chunks(extensions.vector, integer, double precision)
  from public, anon, authenticated;
grant  execute on function public.site_match_chunks(extensions.vector, integer, double precision)
  to service_role;

revoke execute on function public.site_check_rate(text, integer, integer, integer)
  from public, anon, authenticated;
grant  execute on function public.site_check_rate(text, integer, integer, integer)
  to service_role;

commit;
