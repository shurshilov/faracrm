import { useSelector } from 'react-redux';
import { selectCurrentSession } from '@/slices/authSlice';

/**
 * Администратор настроек: суперпользователь или роль system_admin — то же
 * правило, что Session.is_system_admin на бэке. Решает только показ
 * настроек в интерфейсе; доступ к данным держат ACL/Rules на сервере.
 */
export function useIsSystemAdmin(): boolean {
  const user = useSelector(selectCurrentSession)?.user_id;
  return (
    !!user?.is_admin ||
    (user?.role_ids ?? []).some(role => role.code === 'system_admin')
  );
}
