-- Face frame captured during a vision session, so a person can be named (and enrolled) later
alter table sessions add column if not exists face_image_b64 text;
