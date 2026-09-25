-- The host (the account owner) is a person too: a name, a voice print and a face.
alter table known_persons add column if not exists is_self boolean not null default false;
create unique index if not exists known_persons_one_self on known_persons (patient_id) where is_self;
