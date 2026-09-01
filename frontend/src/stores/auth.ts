import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { login as loginRequest, register as registerRequest } from '@/api/auth'
import { getCurrentUser } from '@/api/users'
import {
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from '@/auth/session'
import type { LoginInput, RegisterInput, RegisterResponse } from '@/types/auth'
import type { UserResponse } from '@/types/user'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(getAccessToken())
  const currentUser = ref<UserResponse | null>(null)
  const loading = ref(false)
  const initialized = ref(false)
  const isLoggedIn = computed(() => token.value !== null)

  function clearSession(): void {
    clearAccessToken()
    token.value = null
    currentUser.value = null
  }

  async function login(input: LoginInput): Promise<UserResponse> {
    loading.value = true
    try {
      const tokenResponse = await loginRequest(input)
      setAccessToken(tokenResponse.access_token)
      token.value = tokenResponse.access_token
      currentUser.value = await getCurrentUser()
      return currentUser.value
    } catch (error: unknown) {
      clearSession()
      throw error
    } finally {
      loading.value = false
    }
  }

  async function register(input: RegisterInput): Promise<RegisterResponse> {
    return registerRequest(input)
  }

  async function restoreSession(): Promise<void> {
    if (!token.value) {
      initialized.value = true
      return
    }
    try {
      currentUser.value = await getCurrentUser()
    } catch {
      if (getAccessToken() === null) clearSession()
      else currentUser.value = null
    } finally {
      initialized.value = true
    }
  }

  async function refreshCurrentUser(): Promise<UserResponse> {
    currentUser.value = await getCurrentUser()
    return currentUser.value
  }

  function logout(): void {
    clearSession()
  }

  return {
    token,
    currentUser,
    loading,
    initialized,
    isLoggedIn,
    login,
    register,
    restoreSession,
    refreshCurrentUser,
    clearSession,
    logout,
  }
})
