// Spec: MVP-ADMIN-001 — Auth state management
import { create } from 'zustand';
import { apiClient } from '@/api/client';
import type { ApiError } from '@/types/api';

const TOKEN_KEY = 'neuraldb_token';

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: 'super_admin' | 'db_admin' | 'operator' | 'viewer' | 'api_user';
}

interface LoginResponse {
  access_token: string;
  token_type: string;
}

interface AuthState {
  token: string | null;
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<void>;
  clearError: () => void;
}

function decodeJwtPayload(token: string): AuthUser | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = parts[1];
    // Base64url decode
    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/');
    const jsonStr = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    const data = JSON.parse(jsonStr);
    return {
      id: data.sub ?? data.id ?? '',
      email: data.email ?? '',
      name: data.name ?? data.email ?? '',
      role: data.role ?? 'viewer',
    };
  } catch {
    return null;
  }
}

function loadInitialState(): { token: string | null; user: AuthUser | null; isAuthenticated: boolean } {
  const token = localStorage.getItem(TOKEN_KEY);
  if (!token) {
    return { token: null, user: null, isAuthenticated: false };
  }
  const user = decodeJwtPayload(token);
  if (!user) {
    localStorage.removeItem(TOKEN_KEY);
    return { token: null, user: null, isAuthenticated: false };
  }
  return { token, user, isAuthenticated: true };
}

const initial = loadInitialState();

export const useAuthStore = create<AuthState>((set) => ({
  token: initial.token,
  user: initial.user,
  isAuthenticated: initial.isAuthenticated,
  isLoading: false,
  error: null,

  login: async (email: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      // OAuth2PasswordRequestForm requires form-urlencoded (not JSON)
      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', password);
      const response = await apiClient.postForm<LoginResponse>('/auth/login', formData);
      const token = response.access_token;
      const user = decodeJwtPayload(token);
      if (!user) {
        set({ isLoading: false, error: 'Invalid token received from server.' });
        return;
      }
      localStorage.setItem(TOKEN_KEY, token);
      set({ token, user, isAuthenticated: true, isLoading: false, error: null });
    } catch (err) {
      const apiError = err as ApiError;
      // detail can be string or array (Pydantic validation errors) — always coerce to string
      const raw = apiError?.detail;
      let message: string;
      if (typeof raw === 'string') {
        message = raw;
      } else if (Array.isArray(raw)) {
        message = (raw as Array<{ msg?: string }>).map((e) => e.msg ?? String(e)).join(', ');
      } else {
        message = 'Login failed. Please check your credentials.';
      }
      set({ isLoading: false, error: message });
    }
  },

  logout: () => {
    localStorage.removeItem(TOKEN_KEY);
    set({ token: null, user: null, isAuthenticated: false, error: null });
  },

  refreshToken: async () => {
    try {
      const response = await apiClient.post<LoginResponse>('/auth/refresh');
      const token = response.access_token;
      const user = decodeJwtPayload(token);
      if (!user) {
        localStorage.removeItem(TOKEN_KEY);
        set({ token: null, user: null, isAuthenticated: false });
        return;
      }
      localStorage.setItem(TOKEN_KEY, token);
      set({ token, user, isAuthenticated: true });
    } catch {
      localStorage.removeItem(TOKEN_KEY);
      set({ token: null, user: null, isAuthenticated: false });
    }
  },

  clearError: () => set({ error: null }),
}));
