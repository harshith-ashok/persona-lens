-- Enable pgvector
create extension if not exists vector;

-- Patients
create table patients (
  id uuid primary key default gen_random_uuid(),
  full_name text not null,
  timezone text default 'UTC',
  preferred_language text default 'en',
  active boolean default true,
  created_at timestamptz default now()
);

-- Known persons
create table known_persons (
  id uuid primary key default gen_random_uuid(),
  patient_id uuid references patients(id) on delete cascade,
  name text not null,
  relationship text,
  photo_url text,
  ai_context_prompt text,
  is_active boolean default true,
  last_seen_at timestamptz,
  created_at timestamptz default now()
);

-- Face embeddings
create table face_embeddings (
  id uuid primary key default gen_random_uuid(),
  known_person_id uuid references known_persons(id) on delete cascade,
  embedding vector(512),
  image_url text,
  confidence_score float check (confidence_score between 0 and 1),
  captured_at timestamptz default now()
);
create index on face_embeddings using ivfflat (embedding vector_cosine_ops);

-- Person notes (time-sensitive context)
create table person_notes (
  id uuid primary key default gen_random_uuid(),
  known_person_id uuid references known_persons(id) on delete cascade,
  content text not null,
  note_type text check (note_type in ('general', 'recent_event', 'medical', 'reminder')),
  valid_from timestamptz default now(),
  valid_until timestamptz,
  created_at timestamptz default now()
);

-- Interaction logs (every recognition event, with raw transcript)
create table interaction_logs (
  id uuid primary key default gen_random_uuid(),
  patient_id uuid references patients(id) on delete cascade,
  known_person_id uuid references known_persons(id) on delete set null,
  transcript text,                          -- raw spoken transcript of the encounter
  recognition_confidence float,
  location_hint text,
  ai_generated_prompt text,
  device_type text check (device_type in ('mobile', 'glasses', 'tablet')),
  occurred_at timestamptz default now()
);

-- Interaction summaries (first & last per known person, AI-generated from transcript)
create table interaction_summaries (
  id uuid primary key default gen_random_uuid(),
  known_person_id uuid references known_persons(id) on delete cascade unique,

  -- First interaction
  first_summary text,                       -- AI summary of the first ever interaction
  first_occurred_at timestamptz,
  first_log_id uuid references interaction_logs(id) on delete set null,

  -- Last interaction
  last_summary text,                        -- AI summary of the most recent interaction
  last_occurred_at timestamptz,
  last_log_id uuid references interaction_logs(id) on delete set null,

  updated_at timestamptz default now()
);

-- Auto-update updated_at on interaction_summaries
create or replace function update_summary_timestamp()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger set_summary_updated_at
  before update on interaction_summaries
  for each row execute function update_summary_timestamp();

-- RLS
alter table patients enable row level security;
alter table known_persons enable row level security;
alter table interaction_logs enable row level security;
alter table interaction_summaries enable row level security;
