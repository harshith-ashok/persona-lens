-- Photo gallery: every uploaded image is kept, with each detected face's embedding and match
create table if not exists gallery_images (
  id uuid primary key default gen_random_uuid(),
  patient_id uuid not null references patients(id) on delete cascade,
  file_name text not null,          -- original, under GALLERY_DIR/<patient_id>/
  thumb_name text not null,
  content_type text not null,
  width int,
  height int,
  byte_size int,
  caption text,
  created_at timestamptz default now()
);
create index if not exists gallery_images_patient_idx on gallery_images (patient_id, created_at desc);

create table if not exists gallery_faces (
  id uuid primary key default gen_random_uuid(),
  image_id uuid not null references gallery_images(id) on delete cascade,
  patient_id uuid not null references patients(id) on delete cascade,
  person_id uuid references known_persons(id) on delete set null,   -- null = not identified
  box int[] not null,               -- [top, right, bottom, left] in pixels of the stored image
  embedding vector(128) not null,   -- dlib face encoding
  confidence float,
  source text,                      -- cloud | local | local-fallback | manual
  created_at timestamptz default now()
);
create index if not exists gallery_faces_image_idx on gallery_faces (image_id);
create index if not exists gallery_faces_person_idx on gallery_faces (patient_id, person_id);
-- dlib compares faces by Euclidean distance (match below ~0.6), so index with L2
create index if not exists gallery_faces_embedding_idx on gallery_faces using hnsw (embedding vector_l2_ops);

alter table gallery_images enable row level security;
alter table gallery_faces enable row level security;

create or replace function match_gallery_faces(p_patient uuid, p_query vector(128), p_k int default 50, p_max float default 0.6)
returns table (face_id uuid, image_id uuid, person_id uuid, distance float)
language sql stable as $$
  select f.id, f.image_id, f.person_id, (f.embedding <-> p_query)::float as distance
  from gallery_faces f
  where f.patient_id = p_patient and (f.embedding <-> p_query) < p_max
  order by f.embedding <-> p_query
  limit p_k;
$$;

grant all on all tables in schema public to anon, authenticated, service_role;
grant execute on all functions in schema public to anon, authenticated, service_role;
