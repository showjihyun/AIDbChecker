// Spec: API_SPEC.md — API Client
import type { ApiError } from '@/types/api';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private getAuthHeaders(): Record<string, string> {
    const token = localStorage.getItem('neuraldb_token');
    if (token) {
      return { Authorization: `Bearer ${token}` };
    }
    return {};
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    // Fix #2: Handle 401 — clear token and redirect to login
    if (response.status === 401) {
      localStorage.removeItem('neuraldb_token');
      window.location.href = '/';
      const error: ApiError = {
        detail: 'Session expired. Redirecting to login.',
        code: 'UNAUTHORIZED',
        status: 401,
      };
      throw error;
    }

    if (!response.ok) {
      let errorBody: ApiError;
      try {
        errorBody = await response.json();
      } catch {
        errorBody = {
          detail: response.statusText || 'Unknown error',
          code: 'UNKNOWN',
          status: response.status,
        };
      }
      throw errorBody;
    }

    // Fix #6: Return void-safe for 204 No Content
    if (response.status === 204) {
      return undefined as unknown as T;
    }

    return response.json();
  }

  // Fix #1: Wrap fetch in try/catch for network errors
  private async safeFetch(url: string, init: RequestInit): Promise<Response> {
    try {
      return await fetch(url, init);
    } catch (err) {
      const networkError: ApiError = {
        detail: 'Network error. Check your connection.',
        code: 'NETWORK_ERROR',
        status: 0,
      };
      throw networkError;
    }
  }

  async get<T>(path: string, params?: Record<string, string>): Promise<T> {
    const url = new URL(`${this.baseUrl}${path}`, window.location.origin);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        url.searchParams.set(key, value);
      });
    }

    const response = await this.safeFetch(url.toString(), {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
      },
    });

    return this.handleResponse<T>(response);
  }

  async post<T>(path: string, body?: unknown): Promise<T> {
    const response = await this.safeFetch(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
      },
      body: body ? JSON.stringify(body) : undefined,
    });

    return this.handleResponse<T>(response);
  }

  async put<T>(path: string, body?: unknown): Promise<T> {
    const response = await this.safeFetch(`${this.baseUrl}${path}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
      },
      body: body ? JSON.stringify(body) : undefined,
    });

    return this.handleResponse<T>(response);
  }

  // Fix #6: delete returns Promise<void>
  async delete(path: string): Promise<void> {
    const response = await this.safeFetch(`${this.baseUrl}${path}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
      },
    });

    await this.handleResponse<void>(response);
  }
}

export const apiClient = new ApiClient(BASE_URL);
