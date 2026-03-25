// Spec: MVP-ADMIN-001 — Login page
import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { useAuthStore } from '@/stores/authStore';
import { cn } from '@/lib/cn';

export function LoginPage() {
  const navigate = useNavigate();
  const login = useAuthStore((s) => s.login);
  const isLoading = useAuthStore((s) => s.isLoading);
  const error = useAuthStore((s) => s.error);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const clearError = useAuthStore((s) => s.clearError);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  // Redirect to dashboard if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate({ to: '/' });
    }
  }, [isAuthenticated, navigate]);

  // Clear error when inputs change
  useEffect(() => {
    if (error) clearError();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [email, password]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!email.trim() || !password.trim()) return;
      await login(email.trim(), password);
    },
    [email, password, login]
  );

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center px-4">
      {/* Subtle radial glow behind the form */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            'radial-gradient(ellipse 600px 400px at 50% 40%, rgba(14,165,233,0.06) 0%, transparent 70%)',
        }}
      />

      <div className="relative w-full max-w-sm">
        {/* Logo + Branding */}
        <div className="text-center mb-10">
          <h1 className="text-3xl font-display font-bold text-primary-container tracking-tighter">
            NeuralDB
          </h1>
          <p className="text-xs text-on-surface-variant font-semibold tracking-[0.25em] uppercase mt-1.5">
            Monitoring
          </p>
        </div>

        {/* Login form card */}
        <form
          onSubmit={handleSubmit}
          className="bg-surface-container rounded-xl p-8 shadow-neural-glow"
        >
          <h2 className="text-lg font-display font-bold text-on-surface mb-6">
            Sign In
          </h2>

          {/* Error message */}
          {error && (
            <div
              className="mb-4 rounded-lg bg-error-container/20 px-4 py-3 text-sm text-error"
              role="alert"
            >
              {error}
            </div>
          )}

          {/* Email field */}
          <div className="mb-4">
            <label
              htmlFor="login-email"
              className="block text-xs font-semibold tracking-wider uppercase text-on-surface-variant mb-2"
            >
              Email
            </label>
            <input
              id="login-email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@neuraldb.io"
              className={cn(
                'w-full px-4 py-2.5 rounded-lg text-sm font-sans',
                'bg-surface-container-high text-on-surface placeholder:text-outline',
                'outline-none transition-all duration-200 ease-out',
                'focus:ring-2 focus:ring-primary-container/50 focus:bg-surface-container-highest'
              )}
            />
          </div>

          {/* Password field */}
          <div className="mb-6">
            <label
              htmlFor="login-password"
              className="block text-xs font-semibold tracking-wider uppercase text-on-surface-variant mb-2"
            >
              Password
            </label>
            <input
              id="login-password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="********"
              className={cn(
                'w-full px-4 py-2.5 rounded-lg text-sm font-sans',
                'bg-surface-container-high text-on-surface placeholder:text-outline',
                'outline-none transition-all duration-200 ease-out',
                'focus:ring-2 focus:ring-primary-container/50 focus:bg-surface-container-highest'
              )}
            />
          </div>

          {/* Submit button */}
          <button
            type="submit"
            disabled={isLoading || !email.trim() || !password.trim()}
            className={cn(
              'w-full py-2.5 rounded-lg text-sm font-semibold',
              'transition-all duration-200 ease-out',
              'bg-primary-container text-on-primary',
              'hover:brightness-110 active:scale-[0.98]',
              'disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:brightness-100 disabled:active:scale-100'
            )}
          >
            {isLoading ? (
              <span className="inline-flex items-center gap-2">
                <svg
                  className="animate-spin h-4 w-4"
                  viewBox="0 0 24 24"
                  fill="none"
                  aria-hidden="true"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
                Signing in...
              </span>
            ) : (
              'Sign In'
            )}
          </button>
        </form>

        {/* Footer */}
        <p className="text-center text-xs text-outline mt-6">
          NeuralDB v0.1.0 &middot; MVP
        </p>
      </div>
    </div>
  );
}
