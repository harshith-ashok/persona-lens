// getToken.js
import { createClient } from "@supabase/supabase-js";

const supabase = createClient(
  process.env.SUPABASE_URL ?? "http://localhost:8000",
  process.env.SUPABASE_ANON_KEY,
);

const { data, error } = await supabase.auth.signInWithPassword({
  email: `${process.env.PL_USERNAME.toLowerCase()}@persona-lens.local`,
  password: "pass",
});

console.log(data.session.access_token);
