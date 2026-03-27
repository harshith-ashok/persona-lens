<template>
  <div class="login-root">
    <!-- Animated background grid -->
    <div class="grid-bg"></div>

    <!-- Glow orbs -->
    <div class="orb orb-1"></div>
    <div class="orb orb-2"></div>

    <div class="card">
      <!-- Logo / Brand -->
      <div class="brand">
        <div class="logo-icon">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <circle cx="14" cy="14" r="13" stroke="#6c63ff" stroke-width="1.5" />
            <circle cx="14" cy="14" r="6" fill="#6c63ff" opacity="0.3" />
            <circle cx="14" cy="14" r="3" fill="#6c63ff" />
          </svg>
        </div>
        <span class="brand-name">FaceID</span>
      </div>

      <h1 class="title">Welcome back</h1>
      <p class="subtitle">Sign in to access your dashboard</p>

      <!-- Error / Success messages -->
      <div v-if="errorMsg" class="alert alert-error">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="7" stroke="#ff6b6b" stroke-width="1.5" />
          <path d="M8 5v3M8 10.5v.5" stroke="#ff6b6b" stroke-width="1.5" stroke-linecap="round" />
        </svg>
        {{ errorMsg }}
      </div>
      <div v-if="successMsg" class="alert alert-success">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="7" stroke="#6c63ff" stroke-width="1.5" />
          <path d="M5 8l2 2 4-4" stroke="#6c63ff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        {{ successMsg }}
      </div>

      <!-- Form -->
      <div class="form">
        <!-- Email -->
        <div class="field" :class="{ focused: focusedField === 'email', filled: email }">
          <label>Email address</label>
          <div class="input-wrap">
            <svg class="field-icon" width="16" height="16" viewBox="0 0 16 16" fill="none">
              <rect x="1" y="3" width="14" height="10" rx="2" stroke="currentColor" stroke-width="1.4" />
              <path d="M1 5.5l7 4 7-4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
            </svg>
            <input
              v-model="email"
              type="email"
              placeholder="you@example.com"
              autocomplete="email"
              @focus="focusedField = 'email'"
              @blur="focusedField = ''"
            />
          </div>
        </div>

        <!-- Password -->
        <div class="field" :class="{ focused: focusedField === 'password', filled: password }">
          <label>Password</label>
          <div class="input-wrap">
            <svg class="field-icon" width="16" height="16" viewBox="0 0 16 16" fill="none">
              <rect x="3" y="7" width="10" height="7" rx="1.5" stroke="currentColor" stroke-width="1.4" />
              <path d="M5 7V5a3 3 0 016 0v2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
            </svg>
            <input
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              placeholder="••••••••"
              autocomplete="current-password"
              @focus="focusedField = 'password'"
              @blur="focusedField = ''"
              @keyup.enter="handleLogin"
            />
            <button class="toggle-pw" type="button" @click="showPassword = !showPassword" tabindex="-1">
              <svg v-if="!showPassword" width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M1 8s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5z" stroke="currentColor" stroke-width="1.4" />
                <circle cx="8" cy="8" r="2" stroke="currentColor" stroke-width="1.4" />
              </svg>
              <svg v-else width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M2 2l12 12M6.5 6.7A2 2 0 0010 9.5M4.2 4.5C2.8 5.5 1 8 1 8s2.5 5 7 5c1.4 0 2.6-.4 3.6-1M6 3.2C6.6 3.1 7.3 3 8 3c4.5 0 7 5 7 5s-.6 1.2-1.7 2.3" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
              </svg>
            </button>
          </div>
        </div>

        <!-- Forgot password -->
        <div class="row-between">
          <span></span>
          <button class="link-btn" type="button" @click="handleForgotPassword">Forgot password?</button>
        </div>

        <!-- Login button -->
        <button class="btn-login" :class="{ loading: isLoading }" @click="handleLogin" :disabled="isLoading">
          <span v-if="!isLoading">Sign In</span>
          <span v-else class="spinner-wrap">
            <svg class="spinner" width="18" height="18" viewBox="0 0 18 18">
              <circle cx="9" cy="9" r="7" stroke="white" stroke-width="2" stroke-dasharray="32" stroke-dashoffset="10" fill="none" />
            </svg>
            Signing in…
          </span>
        </button>

        <!-- Sign up -->
        <p class="signup-text">
          Don't have an account?
          <router-link to="/register" class="link-btn">Create one</router-link>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { createClient } from '@supabase/supabase-js'

// ── Supabase setup ──────────────────────────────────────────────────────────
const supabase = createClient(
  'https://pffshbkpvbxakvblflzw.supabase.co',
  'sb_publishable_ilNvaeRqllSPmsbaN2Ro0w_i2GeH6DZ'
)

const router = useRouter()

// ── State ───────────────────────────────────────────────────────────────────
const email       = ref('')
const password    = ref('')
const showPassword = ref(false)
const isLoading   = ref(false)
const focusedField = ref('')
const errorMsg    = ref('')
const successMsg  = ref('')

// ── Helpers ─────────────────────────────────────────────────────────────────
function clearMessages() {
  errorMsg.value = ''
  successMsg.value = ''
}

// ── Login ───────────────────────────────────────────────────────────────────
async function handleLogin() {
  clearMessages()

  if (!email.value || !password.value) {
    errorMsg.value = 'Please fill in all fields.'
    return
  }

  isLoading.value = true

  const { error } = await supabase.auth.signInWithPassword({
    email: email.value,
    password: password.value,
  })

  isLoading.value = false

  if (error) {
    errorMsg.value = error.message
  } else {
    console.log('Login successful!')
    router.push('/dashboard')   // redirect to your face-recognition dashboard
  }
}

// ── Forgot password ─────────────────────────────────────────────────────────
async function handleForgotPassword() {
  clearMessages()

  if (!email.value) {
    errorMsg.value = 'Enter your email address first.'
    return
  }

  const { error } = await supabase.auth.resetPasswordForEmail(email.value, {
    redirectTo: `${window.location.origin}/reset-password`,
  })

  if (error) {
    errorMsg.value = error.message
  } else {
    successMsg.value = 'Password reset link sent — check your inbox.'
  }
}

</script>

<style scoped>
/* ── Variables ─────────────────────────────────────────────────────────── */
:root {
  --accent: #6c63ff;
  --accent-dim: rgba(108, 99, 255, 0.15);
  --accent-glow: rgba(108, 99, 255, 0.4);
  --bg: #000000;
  --surface: #0d0d0d;
  --border: rgba(108, 99, 255, 0.2);
  --text: #f0f0f0;
  --muted: #666;
}

/* ── Root ──────────────────────────────────────────────────────────────── */
.login-root {
  position: relative;
  width: 100vw;
  height: 100vh;
  background: #000;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  font-family: 'Sora', 'Segoe UI', sans-serif;
}

/* ── Grid background ───────────────────────────────────────────────────── */
.grid-bg {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(108, 99, 255, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(108, 99, 255, 0.06) 1px, transparent 1px);
  background-size: 40px 40px;
  mask-image: radial-gradient(ellipse 80% 80% at 50% 50%, black 30%, transparent 100%);
}

/* ── Glow orbs ─────────────────────────────────────────────────────────── */
.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  pointer-events: none;
}
.orb-1 {
  width: 400px;
  height: 400px;
  background: rgba(108, 99, 255, 0.18);
  top: -100px;
  right: -80px;
  animation: drift 8s ease-in-out infinite alternate;
}
.orb-2 {
  width: 300px;
  height: 300px;
  background: rgba(108, 99, 255, 0.1);
  bottom: -80px;
  left: -60px;
  animation: drift 10s ease-in-out infinite alternate-reverse;
}
@keyframes drift {
  from { transform: translate(0, 0) scale(1); }
  to   { transform: translate(30px, 20px) scale(1.05); }
}

/* ── Card ──────────────────────────────────────────────────────────────── */
.card {
  position: relative;
  z-index: 10;
  width: 100%;
  max-width: 420px;
  background: rgba(13, 13, 13, 0.9);
  border: 1px solid rgba(108, 99, 255, 0.2);
  border-radius: 20px;
  padding: 40px;
  backdrop-filter: blur(20px);
  box-shadow:
    0 0 0 1px rgba(108, 99, 255, 0.05),
    0 40px 80px rgba(0, 0, 0, 0.6),
    0 0 60px rgba(108, 99, 255, 0.06);
  animation: cardIn 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
}
@keyframes cardIn {
  from { opacity: 0; transform: translateY(30px) scale(0.97); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

/* ── Brand ─────────────────────────────────────────────────────────────── */
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 28px;
}
.logo-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  background: rgba(108, 99, 255, 0.1);
  border: 1px solid rgba(108, 99, 255, 0.3);
  border-radius: 10px;
}
.brand-name {
  font-size: 18px;
  font-weight: 700;
  color: #fff;
  letter-spacing: 0.5px;
}

/* ── Headings ──────────────────────────────────────────────────────────── */
.title {
  font-size: 26px;
  font-weight: 700;
  color: #fff;
  margin: 0 0 6px;
  letter-spacing: -0.3px;
}
.subtitle {
  font-size: 14px;
  color: #555;
  margin: 0 0 28px;
}

/* ── Alerts ────────────────────────────────────────────────────────────── */
.alert {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 13px;
  margin-bottom: 20px;
}
.alert-error {
  background: rgba(255, 107, 107, 0.08);
  border: 1px solid rgba(255, 107, 107, 0.2);
  color: #ff6b6b;
}
.alert-success {
  background: rgba(108, 99, 255, 0.08);
  border: 1px solid rgba(108, 99, 255, 0.25);
  color: #9d97ff;
}

/* ── Form ──────────────────────────────────────────────────────────────── */
.form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* ── Field ─────────────────────────────────────────────────────────────── */
.field {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.field label {
  font-size: 12px;
  font-weight: 600;
  color: #555;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  transition: color 0.2s;
}
.field.focused label {
  color: #6c63ff;
}

.input-wrap {
  position: relative;
  display: flex;
  align-items: center;
}
.field-icon {
  position: absolute;
  left: 14px;
  color: #444;
  pointer-events: none;
  transition: color 0.2s;
}
.field.focused .field-icon {
  color: #6c63ff;
}

.input-wrap input {
  width: 100%;
  padding: 13px 42px 13px 42px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid #1e1e1e;
  border-radius: 10px;
  color: #f0f0f0;
  font-size: 14px;
  font-family: inherit;
  outline: none;
  transition: border-color 0.25s, box-shadow 0.25s, background 0.25s;
  box-sizing: border-box;
}
.input-wrap input::placeholder { color: #333; }
.input-wrap input:focus {
  border-color: #6c63ff;
  background: rgba(108, 99, 255, 0.05);
  box-shadow: 0 0 0 3px rgba(108, 99, 255, 0.12);
}

/* toggle password */
.toggle-pw {
  position: absolute;
  right: 14px;
  background: none;
  border: none;
  color: #444;
  cursor: pointer;
  display: flex;
  align-items: center;
  padding: 0;
  transition: color 0.2s;
}
.toggle-pw:hover { color: #6c63ff; }

/* ── Row between ───────────────────────────────────────────────────────── */
.row-between {
  display: flex;
  justify-content: flex-end;
  margin-top: -6px;
}

/* ── Link button ───────────────────────────────────────────────────────── */
.link-btn {
  background: none;
  border: none;
  color: #6c63ff;
  font-size: 13px;
  cursor: pointer;
  padding: 0;
  font-family: inherit;
  transition: opacity 0.2s;
  text-decoration: none;
}
.link-btn:hover { opacity: 0.7; }

/* ── Login button ──────────────────────────────────────────────────────── */
.btn-login {
  width: 100%;
  padding: 14px;
  background: #6c63ff;
  color: #fff;
  border: none;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.2s, background 0.2s;
  box-shadow: 0 4px 20px rgba(108, 99, 255, 0.35);
  letter-spacing: 0.3px;
}
.btn-login:hover:not(:disabled) {
  background: #7c74ff;
  box-shadow: 0 6px 28px rgba(108, 99, 255, 0.5);
  transform: translateY(-1px);
}
.btn-login:active:not(:disabled) { transform: translateY(0); }
.btn-login:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-login.loading { pointer-events: none; }

.spinner-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.spinner {
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Sign up ───────────────────────────────────────────────────────────── */
.signup-text {
  text-align: center;
  font-size: 13px;
  color: #444;
  margin: 0;
}
</style>