/**
 * Снимок UI-состояния строки поиска — ровно то, что нужно, чтобы после
 * возврата из формы показать те же чипсы (а не только применить тот же
 * FilterExpression): одиночные триплеты с подписями и И/ИЛИ, применённые
 * сохранённые фильтры, снятые крестиком дефолты и текст быстрого поиска.
 *
 * Пишет <SearchFilter> при каждом изменении, читает он же при монтировании;
 * актуальность снимка (возврат vs новый заход) решает <ViewWrapper>.
 * Хранилище — viewStateStore (sessionStorage).
 */
import type { ActiveFilter, SavedFilter } from './types';

export interface SearchUiState {
  activeFilters: ActiveFilter[];
  appliedSavedFilters: SavedFilter[];
  dismissedDefaults: string[];
  quickSearch: string;
}

export const searchUiKey = (model: string) => `search:${model}`;
