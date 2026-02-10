export interface User {
  id: number;
  name: string;
  home_page?: string | null;
  layout_theme?: 'classic' | 'modern';
  notification_popup?: boolean;
  notification_sound?: boolean;
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
