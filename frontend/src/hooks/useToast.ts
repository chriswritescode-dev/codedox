import toast from 'react-hot-toast';

export const useToast = () => {
  const showSuccess = (message: string) => {
    toast.success(message, {
      duration: 4000,
      position: 'bottom-right',
      style: {
        background: '#10b981',
        color: '#fff',
      },
    });
  };

  const showError = (error: unknown) => {
    const message = error instanceof Error 
      ? error.message 
      : typeof error === 'string' 
        ? error 
        : 'An unexpected error occurred';
    
    toast.error(message, {
      duration: 5000,
      position: 'bottom-right',
      style: {
        background: '#ef4444',
        color: '#fff',
      },
    });
  };

  const showInfo = (message: string) => {
    toast(message, {
      duration: 4000,
      position: 'bottom-right',
      style: {
        background: '#3b82f6',
        color: '#fff',
      },
    });
  };

  const showWarning = (message: string) => {
    toast(message, {
      duration: 4000,
      position: 'bottom-right',
      icon: '⚠️',
      style: {
        background: '#f59e0b',
        color: '#fff',
      },
    });
  };

  return {
    success: showSuccess,
    error: showError,
    info: showInfo,
    warning: showWarning,
  };
};