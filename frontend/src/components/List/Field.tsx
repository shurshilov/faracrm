import { LabelPosition } from '@/components/Form/FormSettingsContext';

export interface FieldProps {
  name: string;
  label?: string;
  labelPosition?: LabelPosition;
  children?: React.ReactNode;
  /** Кастомный рендер для таблицы */
  render?: (value: any, record: any) => React.ReactNode;
  /** Скрыть колонку (но запрашивать данные) */
  hidden?: boolean;
  /** Поля для запроса (для виртуальных колонок или дополнительных данных) */
  fields?: string[];
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

export const Field = ({
  name,
  label,
  labelPosition,
  children,
  render,
  hidden,
  fields,
  virtual,
  ...props
}: FieldProps) => <></>;
