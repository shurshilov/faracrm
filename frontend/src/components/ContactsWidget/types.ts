// ContactsWidget types

/** Тип контакта — динамический строковый код (name из contact_type) */
export type ContactType = string;

export interface ContactTypeConfig {
  id?: number;
  name: string;
  label: string;
  icon: string;
  color: string;
  placeholder: string;
  pattern: string;
  sequence: number;
  connectorTypes: string[];
}

export interface Contact {
  id?: number;
  /** Строковый код типа (для отображения) */
  contact_type: ContactType;
  /** ID записи contact_type (для сохранения в БД) */
  contact_type_id?: number;
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
