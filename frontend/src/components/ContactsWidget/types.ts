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
  /**
   * РЕАЛЬНОЕ значение контакта (+79991234567, ivan@mail.ru, @username, 307).
   * Соответствует полю `value` модели contact — именно по нему идёт матчинг
   * на бэке (find_for_webhook / find_operator_by_value). Виджет работает
   * только с ним; `name` в модели — человекочитаемое описание.
   */
  value: string;
  is_primary: boolean;
  _isNew?: boolean;
  _isDeleted?: boolean;
  /** Значение изменено пользователем — нужно записать в БД (только для id). */
  _isDirty?: boolean;
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
