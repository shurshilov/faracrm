import { Suspense, lazy, useLayoutEffect, useMemo } from 'react';
import LoadingScreen from '@components/LoadingScreen/LoadingScreen';
import { useDispatch, useSelector } from 'react-redux';
import ProtectedLayout from './ProtectedLayout/ProtectedLayout';
import { getSession, selectIsLoggedIn } from '@/slices/authSlice';
import {
  LayoutThemeProvider,
  useLayoutTheme,
  ModernLayout,
} from '@/components/ModernTheme';

// Компонент выбора layout в зависимости от темы
function ThemedLayout() {
  const { layoutTheme } = useLayoutTheme();

  if (layoutTheme === 'modern') {
    return <ModernLayout />;
  }

  return <ProtectedLayout />;
}

export function Layout() {
  const dispatch = useDispatch();
  const authenticated = useSelector(selectIsLoggedIn);
  // navigator.serviceWorker.register('/sw.js');
  console.log(authenticated, 'authenticated');

  useLayoutEffect(() => {
    dispatch(getSession());
  }, [dispatch]);

  const AppLayout = useMemo(() => {
    if (authenticated) {
      // Возвращаем компонент с провайдером темы
      return () => (
        <LayoutThemeProvider>
          <ThemedLayout />
        </LayoutThemeProvider>
      );
    }
    return lazy(() => import('@/fara_base/auth/SignIn'));
  }, [authenticated]);

  return (
    <Suspense
      fallback={
        <div className="flex flex-auto flex-col h-[100vh]">
          <LoadingScreen />
        </div>
      }>
      <AppLayout />
    </Suspense>
  );
}
