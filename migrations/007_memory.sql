-- "Ask your memory": embedded chunks of past conversations (nomic-embed-text, 768-d)
create table if not exists memory_chunks (
  id uuid primary key default gen_random_uuid(),
  patient_id uuid not null references patients(id) on delete cascade,
  session_id uuid references sessions(id) on delete cascade,
  person_id uuid references known_persons(id) on delete set null,
  occurred_at timestamptz not null default now(),
  kind text not null check (kind in ('summary', 'transcript')),
  content text not null,
  embedding vector(768)
);
create index if not exists memory_chunks_patient_idx on memory_chunks (patient_id, occurred_at desc);
create index if not exists memory_chunks_session_idx on memory_chunks (session_id);
create index if not exists memory_chunks_embedding_idx on memory_chunks using hnsw (embedding vector_cosine_ops);
alter table memory_chunks enable row level security;

create or replace function match_memory(p_patient uuid, p_query vector(768), p_k int default 8)
returns table (id uuid, session_id uuid, person_id uuid, occurred_at timestamptz, kind text, content text, similarity float)
language sql stable as $$
  select m.id, m.session_id, m.person_id, m.occurred_at, m.kind, m.content,
         1 - (m.embedding <=> p_query) as similarity
  from memory_chunks m
  where m.patient_id = p_patient and m.embedding is not null
  order by m.embedding <=> p_query
  limit p_k;
$$;

grant all on all tables in schema public to anon, authenticated, service_role;
grant execute on all functions in schema public to anon, authenticated, service_role;
