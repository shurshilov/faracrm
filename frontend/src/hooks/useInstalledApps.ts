import { useCallback, useMemo } from 'react';
import { useGetPublicConfigQuery } from '@/services/config/config';

/**
 * Активные приложения — из публичного конфига ядра (GET /public/config):
 * без модуля apps_install там всё из project_setup, с ним — установленные.
 * Конфиг грузится при старте приложения (BrandingHead).
 *
 * Пока конфиг не пришёл (или запрос упал) — ничего не фильтруем: меню
 * ведёт себя как раньше, а не мигает пустотой на каждом F5.
 */
export function useInstalledApps() {
  const { data } = useGetPublicConfigQuery();

  // Фильтр для меню (см. getVisibleMenuItems): группы активных.
  const installed = useMemo(
    () => (data ? { app_keys: data.app_keys } : null),
    [data],
  );
  const codes = useMemo(() => new Set(data?.apps), [data]);
  const isInstalled = useCallback(
    (code: string) => !data || codes.has(code),
    [data, codes],
  );

  return { installed, isInstalled };
}

/**
 * Строгая проверка одного приложения — для кода, который без него не
 * должен ни грузить, ни показывать своё: undefined — конфиг ещё не
 * пришёл, запрос упал — false.
 */
export function useAppInstalled(code: string): boolean | undefined {
  const { data, isError } = useGetPublicConfigQuery();
  if (isError) return false;
  return data?.apps.includes(code);
}
