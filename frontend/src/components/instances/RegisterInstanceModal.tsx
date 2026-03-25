// Spec: MVP-DASH-001, API_SPEC.md Section 2 — Instance registration modal
import { useState, useCallback, useEffect } from 'react';
import { cn } from '@/lib/cn';
import { useCreateInstance } from '@/api/hooks/useInstances';
import type { CreateInstanceRequest } from '@/types/api';

interface RegisterInstanceModalProps {
  open: boolean;
  onClose: () => void;
}

interface FormData {
  name: string;
  host: string;
  port: string;
  database_name: string;
  db_type: 'postgresql' | 'mysql' | 'mssql';
  environment: 'production' | 'staging' | 'development';
  username: string;
  password: string;
}

interface FormErrors {
  name?: string;
  host?: string;
  port?: string;
  database_name?: string;
  username?: string;
  password?: string;
}

const INITIAL_FORM: FormData = {
  name: '',
  host: '',
  port: '5432',
  database_name: '',
  db_type: 'postgresql',
  environment: 'production',
  username: '',
  password: '',
};

function validate(form: FormData): FormErrors {
  const errors: FormErrors = {};
  if (!form.name.trim()) errors.name = 'Instance name is required.';
  if (!form.host.trim()) errors.host = 'Host address is required.';
  const port = Number(form.port);
  if (!form.port || isNaN(port) || port < 1 || port > 65535) {
    errors.port = 'Port must be between 1 and 65535.';
  }
  if (!form.database_name.trim()) errors.database_name = 'Database name is required.';
  if (!form.username.trim()) errors.username = 'Username is required for connection.';
  if (!form.password.trim()) errors.password = 'Password is required for connection.';
  return errors;
}

export function RegisterInstanceModal({ open, onClose }: RegisterInstanceModalProps) {
  const [form, setForm] = useState<FormData>(INITIAL_FORM);
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);

  const createInstance = useCreateInstance();

  // Reset form state when modal opens
  useEffect(() => {
    if (open) {
      setForm(INITIAL_FORM);
      setErrors({});
      setSubmitError(null);
      createInstance.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Close on Escape key
  useEffect(() => {
    if (!open) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  const handleChange = useCallback(
    (field: keyof FormData) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      setForm((prev) => ({ ...prev, [field]: e.target.value }));
      setErrors((prev) => ({ ...prev, [field]: undefined }));
      setSubmitError(null);
    },
    []
  );

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const validationErrors = validate(form);
      if (Object.keys(validationErrors).length > 0) {
        setErrors(validationErrors);
        return;
      }

      const payload: CreateInstanceRequest = {
        name: form.name.trim(),
        db_type: form.db_type,
        host: form.host.trim(),
        port: Number(form.port),
        database_name: form.database_name.trim(),
        environment: form.environment,
        connection_config: {
          username: form.username.trim(),
          password: form.password,
        },
      };

      createInstance.mutate(payload, {
        onSuccess: () => {
          onClose();
        },
        onError: (err: unknown) => {
          const detail = (err as { detail?: string })?.detail ?? 'Failed to create instance. Check your inputs and try again.';
          setSubmitError(detail);
        },
      });
    },
    [form, createInstance, onClose]
  );

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="register-modal-title"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-surface/80 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal content */}
      <div className="relative w-full max-w-lg mx-4 bg-surface-container rounded-2xl shadow-neural-glow overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-6 pb-2">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary-container/10 flex items-center justify-center">
              <span className="material-symbols-outlined text-primary-container">
                add_circle
              </span>
            </div>
            <div>
              <h2 id="register-modal-title" className="text-base font-semibold text-on-surface">
                Register Instance
              </h2>
              <p className="text-xs text-on-surface-variant">
                Add a PostgreSQL database to monitor
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-on-surface-variant hover:text-on-surface transition-colors duration-200 ease-out p-1 rounded-lg hover:bg-surface-container-high"
            aria-label="Close dialog"
          >
            <span className="material-symbols-outlined text-xl">close</span>
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="px-6 pb-6 pt-2 space-y-4">
          {submitError && (
            <div className="rounded-lg bg-error/10 px-4 py-3 text-xs text-error font-medium">
              {submitError}
            </div>
          )}

          {/* Instance Name */}
          <FieldGroup label="Instance Name" htmlFor="reg-name" error={errors.name}>
            <input
              id="reg-name"
              type="text"
              placeholder="e.g., pg-prod-01"
              value={form.name}
              onChange={handleChange('name')}
              className={fieldClass(!!errors.name)}
              autoFocus
            />
          </FieldGroup>

          {/* Host + Port row */}
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <FieldGroup label="Host" htmlFor="reg-host" error={errors.host}>
                <input
                  id="reg-host"
                  type="text"
                  placeholder="10.0.1.100 or hostname"
                  value={form.host}
                  onChange={handleChange('host')}
                  className={fieldClass(!!errors.host)}
                />
              </FieldGroup>
            </div>
            <FieldGroup label="Port" htmlFor="reg-port" error={errors.port}>
              <input
                id="reg-port"
                type="number"
                min={1}
                max={65535}
                value={form.port}
                onChange={handleChange('port')}
                className={fieldClass(!!errors.port)}
              />
            </FieldGroup>
          </div>

          {/* Database Name */}
          <FieldGroup label="Database Name" htmlFor="reg-dbname" error={errors.database_name}>
            <input
              id="reg-dbname"
              type="text"
              placeholder="mydb"
              value={form.database_name}
              onChange={handleChange('database_name')}
              className={fieldClass(!!errors.database_name)}
            />
          </FieldGroup>

          {/* DB Type + Environment row */}
          <div className="grid grid-cols-2 gap-3">
            <FieldGroup label="DB Type" htmlFor="reg-dbtype">
              <select
                id="reg-dbtype"
                value={form.db_type}
                onChange={handleChange('db_type')}
                className={fieldClass(false)}
              >
                <option value="postgresql">PostgreSQL</option>
                <option value="mysql" disabled>MySQL (Phase 4)</option>
                <option value="mssql" disabled>MS SQL (Phase 4)</option>
              </select>
            </FieldGroup>
            <FieldGroup label="Environment" htmlFor="reg-env">
              <select
                id="reg-env"
                value={form.environment}
                onChange={handleChange('environment')}
                className={fieldClass(false)}
              >
                <option value="production">Production</option>
                <option value="staging">Staging</option>
                <option value="development">Development</option>
              </select>
            </FieldGroup>
          </div>

          {/* Credentials section */}
          <div className="pt-2">
            <p className="text-xs font-semibold tracking-wider uppercase text-on-surface-variant mb-3">
              Connection Credentials
            </p>
            <div className="grid grid-cols-2 gap-3">
              <FieldGroup label="Username" htmlFor="reg-user" error={errors.username}>
                <input
                  id="reg-user"
                  type="text"
                  placeholder="postgres"
                  value={form.username}
                  onChange={handleChange('username')}
                  className={fieldClass(!!errors.username)}
                  autoComplete="off"
                />
              </FieldGroup>
              <FieldGroup label="Password" htmlFor="reg-pass" error={errors.password}>
                <input
                  id="reg-pass"
                  type="password"
                  placeholder="********"
                  value={form.password}
                  onChange={handleChange('password')}
                  className={fieldClass(!!errors.password)}
                  autoComplete="new-password"
                />
              </FieldGroup>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className={cn(
                'px-4 py-2 rounded-lg text-xs font-medium',
                'text-on-surface-variant hover:text-on-surface',
                'hover:bg-surface-container-high transition-colors duration-200 ease-out'
              )}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createInstance.isPending}
              className={cn(
                'px-5 py-2 rounded-lg text-xs font-semibold',
                'bg-primary-container text-on-primary',
                'hover:brightness-110 transition-all duration-200 ease-out',
                'disabled:opacity-50 disabled:cursor-not-allowed',
                'flex items-center gap-2'
              )}
            >
              {createInstance.isPending && (
                <span className="material-symbols-outlined text-sm animate-spin">progress_activity</span>
              )}
              {createInstance.isPending ? 'Registering...' : 'Register Instance'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ---- Shared helpers ---- */

function fieldClass(hasError: boolean): string {
  return cn(
    'w-full px-3 py-2 rounded-lg text-xs text-on-surface',
    'bg-surface placeholder:text-outline',
    'focus:outline-none focus:ring-2 focus:ring-primary-container/50',
    'transition-colors duration-200 ease-out',
    hasError ? 'ring-2 ring-error/50' : ''
  );
}

interface FieldGroupProps {
  label: string;
  htmlFor: string;
  error?: string;
  children: React.ReactNode;
}

function FieldGroup({ label, htmlFor, error, children }: FieldGroupProps) {
  return (
    <div>
      <label htmlFor={htmlFor} className="block text-xs font-medium text-on-surface-variant mb-1.5">
        {label}
      </label>
      {children}
      {error && (
        <p className="text-[10px] text-error mt-1">{error}</p>
      )}
    </div>
  );
}
