// getToken.js
import { createClient } from "@supabase/supabase-js";

const supabase = createClient(
  "https://pffshbkpvbxakvblflzw.supabase.co",
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBmZnNoYmtwdmJ4YWt2YmxmbHp3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ2MDUyMTIsImV4cCI6MjA5MDE4MTIxMn0.4rUiGa7rBz7dwloK6nXHqKx2_2nJj1lQpGM7PZQXMLY",
);

const { data, error } = await supabase.auth.signInWithPassword({
  email: "harshith.7k10@gmail.com",
  password: "pass",
});

console.log(data.session.access_token);
