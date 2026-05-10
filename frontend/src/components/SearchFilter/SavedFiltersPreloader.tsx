/**
 * Прогревает RTK Query кеш сохранённых фильтров: один общий запрос
 * без фильтра по модели, чтобы все последующие useGetSavedFiltersQuery(undefined)
 * получали данные синхронно из кеша.
 *
 * Монтируется в <ThemedLayout> и живёт всю сессию авторизованного
 * пользователя — это держит RTK-подписку, благодаря чему данные не
 * выгружаются по keepUnusedDataFor (60s по умолчанию).
 *
 * Не рендерит ничего: чисто side-effect компонент.
 */
import { useGetSavedFiltersQuery } from './savedFiltersApi';

export function SavedFiltersPreloader() {
  useGetSavedFiltersQuery(undefined);
  return null;
}
