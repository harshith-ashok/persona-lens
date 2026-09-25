-- Reference photos (small base64 JPEG crops) for prompt-based cloud face matching
alter table face_embeddings add column if not exists image_b64 text;
