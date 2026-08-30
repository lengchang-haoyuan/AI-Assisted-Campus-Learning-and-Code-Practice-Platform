export interface UserResponse {
  id: number
  username: string
  email: string
  avatar_url: string | null
  bio: string | null
  is_active: boolean
  created_at: string
}
