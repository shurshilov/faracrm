import { useCallback } from 'react';
import { useSelector } from 'react-redux';
import { selectCurrentSession } from '@/slices/authSlice';

/**
 * Есть ли приложение (ключ группы меню, он же Workspace.app_keys) в
 * «Рабочем месте» текущего пользователя. Суперпользователь видит всё.
 *
 * Курирование презентационное — доступ к данным держат ACL/Rules на бэке.
 * Смысл — не слать запросы, которые заведомо упрутся в отказ: у портального
 * пользователя маркетплейса нет ни чатов, ни активностей, и каждый такой
 * запрос был модалкой «доступ запрещён».
 */
export function useHasWorkspaceApp(): (key: string) => boolean {
  const user = useSelector(selectCurrentSession)?.user_id;
  return useCallback(
    (key: string) =>
      !!user?.is_admin || !!user?.workspace_id?.app_keys?.includes(key),
    [user],
  );
}
