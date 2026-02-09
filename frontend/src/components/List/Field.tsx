import { LabelPosition } from '@/components/Form/FormSettingsContext';
import { FaraRecord } from '@/services/api/crudTypes';

/**
 * Generic Field component for List/Form.
 *
 * Type parameter T enables type-safe field names and render callbacks:
 *   <Field<SchemaUser> name="email" />           // ✅ autocomplete + checked
 *   <Field<SchemaUser> name="nonexistent" />      // ❌ TS error
 *
 * Without T, falls back to FaraRecord (any field name allowed).
 */
export interface FieldProps<T extends FaraRecord = FaraRecord> {
  /** Field name — type-checked against T when generic is provided */
  name: keyof T & string;
  label?: string;
  labelPosition?: LabelPosition;
  children?: React.ReactNode;
  /** Кастомный рендер для таблицы */
  render?: (value: any, record: T) => React.ReactNode;
  /** Скрыть колонку (но запрашивать данные) */
  hidden?: boolean;
  /** Поля для запроса (для виртуальных колонок или дополнительных данных) */
  fields?: (keyof T & string)[];
  /** Виртуальная колонка — не запрашивает данные по name, только по fields */
  virtual?: boolean;
  /**
   * Режим отображения для One2many/Many2many колонок в списке.
   * 'badge' — плашечка (по умолчанию), 'text' — обычный текст.
   */
  relationDisplay?: 'badge' | 'text';
  /**
   * Цвет плашечки для One2many/Many2many колонок (mantine color).
   * Например: 'blue', 'green', 'violet'. По умолчанию — серый.
   */
  badgeColor?: string;
  [key: string]: any;
}

export const Field = <T extends FaraRecord = FaraRecord>({
  name,
  label,
  labelPosition,
  children,
  render,
  hidden,
  fields,
  virtual,
  ...props
}: FieldProps<T>) => <></>;
