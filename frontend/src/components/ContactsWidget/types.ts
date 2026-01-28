// ContactsWidget types

export type ContactType =
  | 'phone'
  | 'email'
  | 'telegram'
  | 'avito'
  | 'vk'
  | 'instagram';

export interface ContactTypeConfig {
  name: ContactType;
  label: string;
  icon: string;
  placeholder: string;
  pattern: string;
  sequence: number;
  connectorTypes: string[];
}

export interface Contact {
  id?: number;
  contact_type: ContactType;
  name: string;
  is_primary: boolean;
  _isNew?: boolean;
  _isDeleted?: boolean;
}

export interface ContactsWidgetProps {
  /** Имя поля в форме */
  name: string;
  /** Текущие контакты */
  value: Contact[];
  /** Callback при изменении */
  onChange: (contacts: Contact[]) => void;
  /** Типы контактов для отображения (по умолчанию все) */
  allowedTypes?: ContactType[];
  /** Максимальное количество контактов */
  maxContacts?: number;
  /** Заблокировать редактирование */
  disabled?: boolean;
  /** Скрыть кнопку "основной" */
  hidePrimary?: boolean;
  /** Лейбл */
  label?: string;
}
