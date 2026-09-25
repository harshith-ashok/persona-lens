-- Keep the unidentified speaker's voice on the session so finalize can attach it to the new person
alter table sessions add column if not exists other_voice_embedding vector(512);
alter table sessions add column if not exists transcript_segments jsonb;
