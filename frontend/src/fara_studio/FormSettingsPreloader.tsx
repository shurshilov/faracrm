/**
 * Прогревает RTK Query кеш общих настроек форм одним запросом при старте,
 * как SavedFiltersPreloader: формы берут свою модель из кеша синхронно и
 * не ждут отдельного запроса. Живёт всю сессию, держит подписку — данные
 * не выгружаются по keepUnusedDataFor. Без студии запроса нет
 * (useFormSettingsEnabled). Ничего не рендерит.
 */
import { useGetFormSettingsQuery } from './formSettingsApi';
import { useFormSettingsEnabled } from './useFormSettings';

export function FormSettingsPreloader() {
  const enabled = useFormSettingsEnabled();
  useGetFormSettingsQuery(undefined, { skip: !enabled });
  return null;
}
