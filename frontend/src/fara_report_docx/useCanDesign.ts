import { useIsSystemAdmin } from '@/hooks/useIsSystemAdmin';

/**
 * Кто может править шаблоны отчётов (конструктор, загрузка DOCX):
 * администратор настроек — то же правило, что ACL report_template на бэке
 * (ReportDocxApp.ROLE_ACL).
 */
export function useCanDesignTemplates(): boolean {
  return useIsSystemAdmin();
}
