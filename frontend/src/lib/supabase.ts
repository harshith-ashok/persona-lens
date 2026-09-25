import { createClient } from '@supabase/supabase-js'

export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY,
)

// GoTrue requires an email, so usernames are mapped to a synthetic one.
export const usernameToEmail = (username: string) =>
  `${username.trim().toLowerCase()}@persona-lens.local`
