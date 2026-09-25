import axios from 'axios'
import { supabase } from './supabase'

export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8120'

export const api = axios.create({ baseURL: API_URL })

api.interceptors.request.use(async (config) => {
  const { data } = await supabase.auth.getSession()
  const token = data?.session?.access_token
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
