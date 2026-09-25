-- wespeaker-voxceleb-resnet34-LM produces 256-d speaker embeddings
alter table host_voice_profile alter column embedding type vector(256);
alter table known_persons alter column voice_embedding type vector(256);
alter table sessions alter column other_voice_embedding type vector(256);
