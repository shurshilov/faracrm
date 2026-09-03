/**
 * Навигация по записям: контекст, который вид-список передаёт форме через
 * location.state при открытии записи.
 *
 * Форма по нему (1) листает соседние записи той же выборки, не возвращаясь
 * в список (RecordPager), и (2) возвращается к списку с его x2m-префильтром
 * (BackToListButton → useBackToList).
 *
 * Соседа ищем по позиции: тот же search с тем же фильтром/сортировкой и
 * start=index±1, end=index±2 (один id). Так пейджер идёт по ВСЕЙ выборке,
 * а не только по загруженной странице, и ничего не хранит, кроме позиции.
 */
import type { FilterExpression, GetListParams } from '@/services/api/crudTypes';

/** Параметры выборки списка, в которой открыта запись. */
export interface RecordNavQuery {
  model: string;
  filter?: FilterExpression;
  sort: string;
  order: 'asc' | 'desc';
}

export interface RecordNavContext {
  query: RecordNavQuery;
  /** Позиция записи в выборке (с нуля). */
  index: number;
  /** Размер выборки на момент открытия/последнего шага. */
  total: number;
  /** x2m-префильтр списка (location.state.initialFilter) — вернуть при «К списку». */
  initialFilter?: FilterExpression;
}

/** Форма location.state на маршруте формы. */
export interface RecordNavState {
  recordNav?: RecordNavContext;
}

export function buildRecordNav(
  args: Pick<GetListParams, 'model' | 'filter' | 'sort' | 'order'>,
  index: number,
  total: number | string,
  initialFilter?: FilterExpression,
): RecordNavContext {
  return {
    query: {
      model: args.model,
      filter: args.filter,
      sort: args.sort || 'id',
      order: args.order || 'asc',
    },
    index,
    // Бэк отдаёт total строкой (str(count_total)) — приводим, иначе
    // index < total - 1 сработает, а index + 1 склеит строку.
    total: Number(total),
    initialFilter,
  };
}

export function readRecordNav(state: unknown): RecordNavContext | null {
  return (state as RecordNavState | null)?.recordNav ?? null;
}
