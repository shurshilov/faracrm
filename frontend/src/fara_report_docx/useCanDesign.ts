import { useSelector } from 'react-redux';

/**
 * Кто может править шаблоны отчётов (конструктор, загрузка DOCX):
 * суперпользователь или роль system_admin — то же правило, что ACL
 * report_template на бэке (ReportDocxApp.ROLE_ACL).
 */
export function useCanDesignTemplates(): boolean {
  const session = useSelector((state: any) => state.auth.session);
  const user = session?.user_id;
  return (
    !!user?.is_admin ||
    (user?.role_ids ?? []).some(
      (role: { code: string }) => role.code === 'system_admin',
    )
  );
}
