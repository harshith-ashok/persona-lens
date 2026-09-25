-- Life timeline: decisions, activities, events, money and to-dos found in conversations (or added by hand)
create table if not exists life_events (
  id uuid primary key default gen_random_uuid(),
  patient_id uuid not null references patients(id) on delete cascade,
  session_id uuid references sessions(id) on delete set null,
  person_id uuid references known_persons(id) on delete set null,
  kind text not null check (kind in ('decision', 'activity', 'event', 'money', 'task')),
  title text not null,
  detail text,
  occurs_on date,                      -- when it happened, or when it is due (null = not mentioned)
  amount numeric,
  currency text,
  is_done boolean not null default false,
  source text not null default 'auto' check (source in ('auto', 'manual')),
  created_at timestamptz default now()
);
create index if not exists life_events_patient_idx on life_events (patient_id, occurs_on desc nulls last, created_at desc);
create index if not exists life_events_session_idx on life_events (session_id);
alter table life_events enable row level security;

-- events are searchable by "Ask your memory" too
alter table memory_chunks drop constraint if exists memory_chunks_kind_check;
alter table memory_chunks add constraint memory_chunks_kind_check check (kind in ('summary', 'transcript', 'event'));
alter table memory_chunks add column if not exists event_id uuid references life_events(id) on delete cascade;

-- optional video of a vision session
alter table sessions add column if not exists video_name text;

grant all on all tables in schema public to anon, authenticated, service_role;
