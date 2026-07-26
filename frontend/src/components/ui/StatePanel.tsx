import type { ReactNode } from 'react';
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline';
import { Button } from './Button';

export function LoadingPanel({ label = 'Cargando...' }: { label?: string }) {
  return (
    <div
      className="flex flex-col items-center justify-center h-full py-16 gap-3 text-gray-400 dark:text-gray-500"
      role="status"
      aria-live="polite"
    >
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      <p className="text-sm">{label}</p>
    </div>
  );
}

export function ErrorPanel({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full py-16 gap-3 text-center px-4" role="alert">
      <ExclamationTriangleIcon className="w-10 h-10 text-red-400" />
      <p className="text-sm text-gray-600 dark:text-gray-300 max-w-sm">{message}</p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Reintentar
        </Button>
      )}
    </div>
  );
}

interface EmptyPanelProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyPanel({ icon, title, description, action }: EmptyPanelProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full py-16 gap-2 text-center px-4">
      {icon && <div className="text-4xl mb-1">{icon}</div>}
      <p className="font-medium text-gray-600 dark:text-gray-300">{title}</p>
      {description && <p className="text-sm text-gray-400 dark:text-gray-500">{description}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}
