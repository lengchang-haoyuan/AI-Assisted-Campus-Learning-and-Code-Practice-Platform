import axios from 'axios'

const fallbackBaseUrl = 'http://127.0.0.1:8000/api/v1'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || fallbackBaseUrl,
  timeout: 5000,
  headers: {
    Accept: 'application/json',
  },
})

