-- Sessions, voice profiles and related column changes (idempotent)

create table if not exists sessions (
  id uuid primary key default gen_random_uuid(),
  patient_id uuid not null references patients(id) on delete cascade,
  person_id uuid references known_persons(id) on delete set null,   -- null until identified/named
  mode text not null check (mode in ('vision', 'audio')),
  status text not null default 'open' check (status in ('open', 'ended', 'resolved')),
  summary text,                                                     -- held until a person is attached
  started_at timestamptz default now(),
  ended_at timestamptz
);
create index if not exists sessions_patient_idx on sessions (patient_id, started_at desc);

create table if not exists host_voice_profile (
  patient_id uuid primary key references patients(id) on delete cascade,
  embedding vector(512),
  sample_audio_ref text,
  created_at timestamptz default now()
);

alter table known_persons add column if not exists voice_embedding vector(512);

-- known_person_id is already nullable on interaction_logs
alter table interaction_logs add column if not exists session_id uuid references sessions(id) on delete set null;
alter table interaction_logs add column if not exists mode text check (mode in ('vision', 'audio'));

-- face_recognition (dlib) produces 128-d encodings; the fallback path keeps using them.
drop index if exists face_embeddings_embedding_idx;
alter table face_embeddings alter column embedding type vector(128);
create index if not exists face_embeddings_embedding_idx
  on face_embeddings using hnsw (embedding vector_cosine_ops);

alter table sessions enable row level security;
alter table host_voice_profile enable row level security;

grant all on all tables in schema public to anon, authenticated, service_role;
