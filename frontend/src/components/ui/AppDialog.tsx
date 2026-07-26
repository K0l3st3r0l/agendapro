import { Fragment } from 'react';
import type { MutableRefObject, ReactNode } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import { XMarkIcon } from '@heroicons/react/24/outline';
import { IconButton } from './Button';

const maxWidthClass = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-xl',
  '3xl': 'max-w-3xl',
} as const;

interface AppDialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  maxWidth?: keyof typeof maxWidthClass;
  initialFocus?: MutableRefObject<HTMLElement | null>;
}

export default function AppDialog({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  maxWidth = 'md',
  initialFocus,
}: AppDialogProps) {
  return (
    <Transition show={open} as={Fragment}>
      <Dialog onClose={onClose} className="relative z-50" initialFocus={initialFocus}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-150"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-100"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/50" aria-hidden="true" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-150"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-100"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel className={`w-full ${maxWidthClass[maxWidth]} bg-white dark:bg-gray-800 rounded-2xl shadow-2xl max-h-[90vh] flex flex-col`}>
                <div className="flex items-start justify-between gap-4 px-4 sm:px-6 py-4 border-b border-gray-100 dark:border-gray-700 shrink-0">
                  <div className="min-w-0">
                    <Dialog.Title className="text-lg font-semibold text-gray-900 dark:text-white truncate">
                      {title}
                    </Dialog.Title>
                    {description && (
                      <Dialog.Description className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                        {description}
                      </Dialog.Description>
                    )}
                  </div>
                  <IconButton label="Cerrar" onClick={onClose} className="shrink-0 -mr-2 -mt-1">
                    <XMarkIcon className="w-5 h-5" />
                  </IconButton>
                </div>

                <div className="px-4 sm:px-6 py-4 overflow-y-auto">{children}</div>

                {footer && (
                  <div className="px-4 sm:px-6 py-4 border-t border-gray-100 dark:border-gray-700 shrink-0">
                    {footer}
                  </div>
                )}
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}
