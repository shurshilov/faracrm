/**
 * FaraRecord — базовый тип для generic-компонентов (List, Form, Kanban, Gantt).
 *
 * [key: string]: any сохранён для обратной совместимости.
 * Конкретные views должны использовать типы из '@/types/records':
 *   List<LeadRecord>, Form<TaskRecord>, Kanban<SaleRecord>
 *
 * @see '@/types/records' — канонический источник типов для каждой модели
 */
export interface FaraRecord {
  id: Identifier;
  [key: string]: any;
}
export type VirtualIdType = 'VirtualId';
export const VirtualId = 'VirtualId';

// export interface GetListParams {
//   pagination: PaginationPayload;
//   sort: SortPayload;
//   filter: any;
//   meta?: any;
// }
// export interface GetListResult<RecordType extends RaRecord = any> {}

export type Identifier = string | number;

export type Triplet = [string, string, any];
// Вложенная группа (FilterExpression как элемент) поддерживается бэком
// (filter_parser.py: рекурсивный парс + авто-скобки) и используется
// mergeFilters для безопасной AND-склейки выражений с внутренним OR.
export type FilterItem = Triplet | 'and' | 'or' | FilterExpression;
export type FilterExpression = FilterItem[];

/**
 * Элемент fields в search: имя поля ИЛИ {имя: {fields, filter}} для
 * relation-поля — вложенные поля и фильтр на связанные записи (колонка-
 * связь с пользовательским фильтром, см. ColumnRelationSettings). Бэк
 * складывает filter с фильтром самого поля по И.
 */
export type NestedFieldSpec = { fields?: string[]; filter?: FilterExpression };
export type SearchField = string | Record<string, NestedFieldSpec>;

export type GetListParams = {
  model: string;
  fields: SearchField[];
  end?: number | null;
  order?: 'desc' | 'asc';
  sort?: string;
  start?: number | null;
  limit?: number;
  filter?: FilterExpression;
  raw?: boolean;
};

export type GetListM2mParams = {
  model: string;
  id: number;
  name: string;
  fields: string[];
  start?: number | null;
  end?: number | null;
  order?: 'desc' | 'asc';
  sort?: string;
  limit?: number;
};
/** Вариант Selection-поля как его отдаёт бэкенд: [значение, подпись]. */
export type SelectionOption = [string, string];
export interface GetListField {
  name: string;
  type: string;
  relation?: string;
  /** Для Selection-полей бэкенд (get_fields_info_list) отдаёт варианты. */
  options?: SelectionOption[];
  required?: boolean;
}
export interface GetFormField {
  name: string;
  type: string;
  relatedModel?: string;
  relatedField?: string;
  options?: SelectionOption[];
  required?: boolean;
}
export interface GetListResult<RecordType extends FaraRecord> {
  data: RecordType[];
  total: number;
  fields: GetListField[];
}

export type DeleteListParams = {
  model: string;
  ids: Identifier[];
};
export type DeleteListResult = true;

export type UpdateBulkParams = {
  model: string;
  ids: Identifier[];
  /** Поля, которые выставляются всем выбранным записям одинаково. */
  values: Record<string, any>;
};
export type UpdateBulkResult = Record<string, any>;

export type ReadResult<RecordType extends FaraRecord> = {
  data: RecordType;
  fields: Record<string, GetListField>;
};

export type ReadParams = {
  model: string;
  id: Identifier;
  fields?: string[];
};

export type ReadDefaultValuesResult<RecordType extends FaraRecord> = {
  data: RecordType;
  fields: Record<string, GetListField>;
};

export type ReadDefaultValuesParams = {
  model: string;
  fields?: string[];
};

export type EditResult<RecordType extends FaraRecord> = RecordType;
export type EditParams<RecordType extends FaraRecord> = {
  model: string;
  id: Identifier;
  values: Partial<RecordType>;
  invalidateTags?: string[];
};

export type CreateResult = {
  id: Identifier;
};
export type CreateParams<RecordType> = {
  model: string;
  values: Partial<RecordType>;
};

export type GetAttachmentParams = {
  id: number;
};
