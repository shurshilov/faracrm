import { RoleRecord } from '@/types/records';

export interface User {
  id: number;
  name: string;
  home_page?: string | null;
  layout_theme?: 'classic' | 'modern';
  notification_popup?: boolean;
  notification_sound?: boolean;
  /** Канал звонилки по умолчанию. Пусто — внутренний звонок сотруднику. */
  call_connector_id?: { id: number; name?: string } | null;
  is_admin: boolean;
  role_ids: RoleRecord[];
  /** Активное «Рабочее место»: app_keys — ключи групп меню его приложений
   *  (см. signin на бэке). Нет РМ → null. */
  workspace_id?: { id: number; name: string; app_keys: string[] } | null;
}
export interface Session {
  id: number;
  active: boolean;
  user_id: User;
  token: string;
  ttl: number;

  create_datetime: string;
  create_user_id: number;
  update_datetime: string;
  update_user_id: number;
}
export interface UserInput {
  login: string;
  password: string;
}
