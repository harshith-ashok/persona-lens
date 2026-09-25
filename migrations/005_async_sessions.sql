-- Sessions are processed in the background: open -> processing -> ended | resolved | failed
alter table sessions drop constraint if exists sessions_status_check;
alter table sessions add constraint sessions_status_check
  check (status in ('open', 'processing', 'ended', 'resolved', 'failed'));
alter table sessions add column if not exists error text;
alter table sessions add column if not exists timings jsonb;   -- per-stage seconds, for load testing
