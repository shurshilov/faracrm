import { useCallback, useMemo } from 'react';
import { useGetAppsCatalogQuery } from './api';

/**
 * Установленные приложения из общего RTK-кеша каталога (GET /apps/catalog).
 *
 * Пока каталог не загружен (или запрос упал) — ничего не фильтруем: меню
 * ведёт себя как раньше, а не мигает пустотой на каждом F5.
 */
export function useInstalledApps() {
  const { data } = useGetAppsCatalogQuery();

  // Фильтр для меню (см. getVisibleMenuItems): группы установленных.
  const installed = useMemo(
    () => (data ? { app_keys: data.app_keys } : null),
    [data],
  );
  const codes = useMemo(
    () => new Set(data?.apps.filter(app => app.installed).map(app => app.code)),
    [data],
  );
  const isInstalled = useCallback(
    (code: string) => !data || codes.has(code),
    [data, codes],
  );

  return { installed, isInstalled };
}
