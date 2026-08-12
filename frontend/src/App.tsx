import { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ThemeProvider, useTheme } from './contexts/ThemeContext';
import Layout from './components/Layout';
import { ALLOW_REGISTRATION } from './config/env';

const Login = lazy(() => import('./pages/Login'));
const Register = lazy(() => import('./pages/Register'));
const CalendarPage = lazy(() => import('./pages/CalendarPage'));
const AIConstructor = lazy(() => import('./pages/AIConstructor'));
const Documents = lazy(() => import('./pages/Documents'));
const Settings = lazy(() => import('./pages/Settings'));
const LessonPresenter = lazy(() => import('./pages/LessonPresenter'));
const Lessons = lazy(() => import('./pages/Lessons'));
const LessonBuilder = lazy(() => import('./pages/LessonBuilder'));

const PageFallback = () => (
  <div className="flex items-center justify-center h-full py-24">
    <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary-600" />
  </div>
);

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[100dvh]">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary-600" />
      </div>
    );
  }
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
};

const AppToaster = () => {
  const { theme } = useTheme();
  return (
    <Toaster
      position="top-right"
      toastOptions={{
        duration: 3000,
        style: theme === 'dark'
          ? { background: '#1f2937', color: '#f3f4f6', border: '1px solid #374151' }
          : { background: '#ffffff', color: '#111827', border: '1px solid #e5e7eb' },
      }}
    />
  );
};

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <AppToaster />
          <Suspense fallback={<PageFallback />}>
            <Routes>
              <Route path="/login" element={<Login />} />
              {ALLOW_REGISTRATION && <Route path="/register" element={<Register />} />}
              <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
                <Route index element={<Navigate to="/calendario" replace />} />
                <Route path="calendario" element={<CalendarPage />} />
                <Route path="constructor" element={<AIConstructor />} />
                <Route path="documentos" element={<Documents />} />
                <Route path="clases" element={<Lessons />} />
                <Route path="clases/nueva" element={<LessonBuilder />} />
                <Route path="clases/:id/editar" element={<LessonBuilder />} />
                <Route path="configuracion" element={<Settings />} />
              </Route>
              {/* Fuera del <Layout /> a propósito: sobre el proyector no puede
                  haber sidebar ni encabezado de la app. Sigue protegida. */}
              <Route
                path="/clases/:id/presentar"
                element={<ProtectedRoute><LessonPresenter /></ProtectedRoute>}
              />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
