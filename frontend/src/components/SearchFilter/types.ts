/**
 * Типы для компонента SearchFilter
 */

// Типы полей
export type FieldType =
  | 'Char'
  | 'Text'
  | 'Integer'
  | 'BigInteger'
  | 'SmallInteger'
  | 'Float'
  | 'Boolean'
  | 'Date'
  | 'Datetime'
  | 'Selection'
  | 'Many2one'
  | 'One2many'
  | 'Many2many'
  | 'PolymorphicMany2one'
  | 'PolymorphicOne2many';

// Операторы для разных типов полей
export type StringOperator =
  | '='
  | 'like'
  | 'ilike'
  | '=like'
  | '=ilike'
  | 'not like'
  | 'not ilike'
  | '!=';
export type NumberOperator = '=' | '!=' | '>' | '<' | '>=' | '<=';
export type BooleanOperator = '=' | '!=';
export type RelationOperator = '=' | '!=' | 'in' | 'not in';
export type DateOperator = '=' | '!=' | '>' | '<' | '>=' | '<=';

export type Operator =
  | StringOperator
  | NumberOperator
  | BooleanOperator
  | RelationOperator
  | DateOperator;

// Информация о поле
export interface FieldInfo {
  name: string;
  type: FieldType;
  label?: string;
  relation?: string;
  options?: string[];
}

// Один фильтр (триплет)
export interface FilterTriplet {
  field: string;
  operator: Operator;
  value: any;
}

// Активный фильтр с id для управления
export interface ActiveFilter extends FilterTriplet {
  id: string;
  label: string;
  /** Как этот фильтр соединяется с предыдущим */
  combineWithPrev?: 'and' | 'or';
}

// Сохранённый фильтр
export interface SavedFilter {
  id: string;
  name: string;
  filters: FilterTriplet[];
  createdAt: number;
  isGlobal?: boolean;
  isDefault?: boolean;
}

// Предустановленный фильтр (из кода)
export interface PresetFilter {
  id: string;
  name: string;
  icon?: string;
  filters: FilterTriplet[];
}

// Пропсы для SearchFilter
export interface SearchFilterProps {
  model: string;
  /** Callback при изменении фильтров (возвращает FilterExpression с AND/OR) */
  onFiltersChange: (filters: any[]) => void; // FilterExpression
  /** Предустановленные фильтры из кода */
  presetFilters?: PresetFilter[];
  /** Начальные активные фильтры */
  initialFilters?: FilterTriplet[];
  /** Показывать ли быстрый поиск */
  showQuickSearch?: boolean;
  /** Поле для быстрого поиска (по умолчанию 'name') */
  quickSearchField?: string;
}

// Маппинг типов полей на доступные операторы
export const OPERATORS_BY_FIELD_TYPE: Record<
  string,
  { value: Operator; label: string }[]
> = {
  // Строковые типы
  Char: [
    { value: 'ilike', label: 'содержит' },
    { value: 'not ilike', label: 'не содержит' },
    { value: '=', label: 'равно' },
    { value: '!=', label: 'не равно' },
    { value: 'like', label: 'содержит (регистр)' },
    { value: 'not like', label: 'не содержит (регистр)' },
  ],
  Text: [
    { value: 'ilike', label: 'содержит' },
    { value: 'not ilike', label: 'не содержит' },
    { value: '=', label: 'равно' },
    { value: '!=', label: 'не равно' },
  ],

  // Числовые типы
  Integer: [
    { value: '=', label: '=' },
    { value: '!=', label: '≠' },
    { value: '>', label: '>' },
    { value: '<', label: '<' },
    { value: '>=', label: '≥' },
    { value: '<=', label: '≤' },
  ],
  BigInteger: [
    { value: '=', label: '=' },
    { value: '!=', label: '≠' },
    { value: '>', label: '>' },
    { value: '<', label: '<' },
    { value: '>=', label: '≥' },
    { value: '<=', label: '≤' },
  ],
  SmallInteger: [
    { value: '=', label: '=' },
    { value: '!=', label: '≠' },
    { value: '>', label: '>' },
    { value: '<', label: '<' },
    { value: '>=', label: '≥' },
    { value: '<=', label: '≤' },
  ],
  Float: [
    { value: '=', label: '=' },
    { value: '!=', label: '≠' },
    { value: '>', label: '>' },
    { value: '<', label: '<' },
    { value: '>=', label: '≥' },
    { value: '<=', label: '≤' },
  ],

  // Boolean
  Boolean: [
    { value: '=', label: 'равно' },
    { value: '!=', label: 'не равно' },
  ],

  // Даты
  Date: [
    { value: '=', label: '=' },
    { value: '!=', label: '≠' },
    { value: '>', label: 'после' },
    { value: '<', label: 'до' },
    { value: '>=', label: 'с' },
    { value: '<=', label: 'по' },
  ],
  Datetime: [
    { value: '=', label: '=' },
    { value: '!=', label: '≠' },
    { value: '>', label: 'после' },
    { value: '<', label: 'до' },
    { value: '>=', label: 'с' },
    { value: '<=', label: 'по' },
  ],

  // Отношения
  Many2one: [
    { value: '=', label: '=' },
    { value: '!=', label: '≠' },
  ],
  Many2many: [
    { value: 'in', label: 'содержит' },
    { value: 'not in', label: 'не содержит' },
  ],
  One2many: [
    { value: 'in', label: 'содержит' },
    { value: 'not in', label: 'не содержит' },
  ],
  PolymorphicMany2one: [
    { value: '=', label: '=' },
    { value: '!=', label: '≠' },
  ],
  PolymorphicOne2many: [
    { value: 'in', label: 'содержит' },
    { value: 'not in', label: 'не содержит' },
  ],

  // Selection (как строка)
  Selection: [
    { value: '=', label: 'равно' },
    { value: '!=', label: 'не равно' },
  ],
};

// Получить операторы для типа поля
export function getOperatorsForFieldType(
  fieldType: string,
): { value: Operator; label: string }[] {
  return OPERATORS_BY_FIELD_TYPE[fieldType] || OPERATORS_BY_FIELD_TYPE.Char;
}

// Проверка является ли поле текстовым (для быстрого поиска)
export function isTextFieldType(fieldType: string): boolean {
  return ['Char', 'Text'].includes(fieldType);
}

// Генерация уникального ID
export function generateFilterId(): string {
  return `filter_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

// Форматирование фильтра в читаемую строку
export function formatFilterLabel(
  filter: FilterTriplet,
  fields: FieldInfo[],
): string {
  const fieldInfo = fields.find(f => f.name === filter.field);
  const fieldLabel = fieldInfo?.label || filter.field;

  const operatorInfo = getOperatorsForFieldType(fieldInfo?.type || 'Char').find(
    op => op.value === filter.operator,
  );
  const operatorLabel = operatorInfo?.label || filter.operator;

  let valueLabel = String(filter.value);
  if (filter.value === true) valueLabel = 'Да';
  if (filter.value === false) valueLabel = 'Нет';
  if (filter.value === null || filter.value === undefined) valueLabel = 'пусто';

  return `${fieldLabel} ${operatorLabel} "${valueLabel}"`;
}
