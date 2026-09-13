/**
 * useColumnConfig — per-user, per-model выбор колонок списка.
 *
 * Источник истины для рендера — `selected` (итоговый порядок видимых
 * колонок). По умолчанию это колонки вью (`defaultVisible`, из <Field>).
 * Если пользователь настроил колонки — берём его сохранённый набор с
 * сервера (модель column_settings). Там же — настройки колонок-связей:
 * виджет (`widgets`) и фильтр на связанные записи (`filters`).
 *
 * Живые правки применяются мгновенно (`setDraft` → таблица перестраивается),
 * а на сервер пишутся один раз при закрытии меню (`persistIfDirty`) —
 * так нет гонок create-дубликатов и лишних запросов на каждый чек-бокс.
 */
import { useCallback, useMemo, useRef, useState } from 'react';
import type { FilterExpression } from '@/services/api/crudTypes';
import {
  useGetColumnSettingsQuery,
  useCreateColumnSettingsMutation,
  useUpdateColumnSettingsMutation,
  useDeleteColumnSettingsMutation,
  RelationColumnWidget,
  RelationColumnWidgets,
  RelationColumnFilters,
} from './columnSettingsApi';

export interface ColumnConfig {
  /** Итоговый список видимых колонок в порядке отображения. */
  selected: string[];
  /** Виджеты колонок-связей по имени поля. */
  widgets: RelationColumnWidgets;
  /** Фильтры на связанные записи по имени поля. */
  filters: RelationColumnFilters;
  /** Отличается ли текущая настройка от колонок вью по умолчанию. */
  isCustom: boolean;
  /** Идёт первичная загрузка настройки с сервера. */
  isLoading: boolean;
  /** Живое изменение выбора (мгновенно перестраивает таблицу). */
  setDraft: (cols: string[]) => void;
  /** Виджет колонки-связи (null — по умолчанию). */
  setWidget: (field: string, widget: RelationColumnWidget | null) => void;
  /** Фильтр колонки-связи (пусто — без фильтра). */
  setFilter: (field: string, filter: FilterExpression | null) => void;
  /** Записать текущий выбор на сервер, если он менялся с прошлого раза. */
  persistIfDirty: () => void;
  /** Вернуть колонки вью по умолчанию (удаляет строку на сервере). */
  reset: () => void;
}

function arraysEqual(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== b[i]) return false;
  }
  return true;
}

function parseJson<T>(raw: string | null | undefined, fallback: T): T {
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

/** Убрать пустые записи (null/[]), чтобы «сброшено» не хранилось. */
function compact<T>(map: Record<string, T | null>): Record<string, T> {
  const out: Record<string, T> = {};
  for (const [key, value] of Object.entries(map)) {
    if (value == null) continue;
    if (Array.isArray(value) && value.length === 0) continue;
    out[key] = value;
  }
  return out;
}

export function useColumnConfig(
  model: string,
  defaultVisible: string[],
): ColumnConfig {
  const { data: row, isLoading } = useGetColumnSettingsQuery(model);
  const [createSettings] = useCreateColumnSettingsMutation();
  const [updateSettings] = useUpdateColumnSettingsMutation();
  const [deleteSettings] = useDeleteColumnSettingsMutation();

  // Колонки, сохранённые пользователем (или null, если не настраивал).
  const serverCols = useMemo<string[] | null>(() => {
    const parsed = parseJson<unknown>(row?.columns, null);
    if (!Array.isArray(parsed)) return null;
    return parsed.filter((x): x is string => typeof x === 'string');
  }, [row?.columns]);
  const serverWidgets = useMemo<RelationColumnWidgets>(
    () => parseJson<RelationColumnWidgets>(row?.widgets, {}),
    [row?.widgets],
  );
  const serverFilters = useMemo<RelationColumnFilters>(
    () => parseJson<RelationColumnFilters>(row?.filters, {}),
    [row?.filters],
  );

  // Несохранённые правки текущей сессии. null = «правок нет».
  const [draft, setDraftState] = useState<string[] | null>(null);
  const [draftWidgets, setDraftWidgets] =
    useState<RelationColumnWidgets | null>(null);
  const [draftFilters, setDraftFilters] =
    useState<RelationColumnFilters | null>(null);

  // id строки на сервере: из кеша ИЛИ из ответа create — чтобы второе
  // сохранение делало update, а не плодило дубликаты до рефетча.
  const [localRowId, setLocalRowId] = useState<number | undefined>(undefined);
  const rowId = row?.id ?? localRowId;

  const dirtyRef = useRef(false);

  const selected = draft ?? serverCols ?? defaultVisible;
  const widgets = draftWidgets ?? serverWidgets;
  const filters = draftFilters ?? serverFilters;
  const hasRelationSettings =
    Object.keys(widgets).length > 0 || Object.keys(filters).length > 0;
  const isCustom =
    !arraysEqual(selected, defaultVisible) || hasRelationSettings;

  const setDraft = useCallback((cols: string[]) => {
    dirtyRef.current = true;
    setDraftState(cols);
  }, []);

  const setWidget = useCallback(
    (field: string, widget: RelationColumnWidget | null) => {
      dirtyRef.current = true;
      setDraftWidgets(prev =>
        compact({ ...(prev ?? serverWidgets), [field]: widget }),
      );
    },
    [serverWidgets],
  );

  const setFilter = useCallback(
    (field: string, filter: FilterExpression | null) => {
      dirtyRef.current = true;
      setDraftFilters(prev =>
        compact({ ...(prev ?? serverFilters), [field]: filter }),
      );
    },
    [serverFilters],
  );

  const persistIfDirty = useCallback(async () => {
    if (!dirtyRef.current) return;
    dirtyRef.current = false;

    const cols = draft ?? serverCols ?? defaultVisible;
    const nextWidgets = draftWidgets ?? serverWidgets;
    const nextFilters = draftFilters ?? serverFilters;
    const relationEmpty =
      Object.keys(nextWidgets).length === 0 &&
      Object.keys(nextFilters).length === 0;

    // Всё снова как в вью по умолчанию — отдельную запись не храним.
    if (arraysEqual(cols, defaultVisible) && relationEmpty) {
      if (rowId) {
        const id = rowId;
        setLocalRowId(undefined);
        await deleteSettings({ id, model_name: model });
      }
      return;
    }

    const payload = {
      columns: JSON.stringify(cols),
      widgets: relationEmpty ? null : JSON.stringify(nextWidgets),
      filters: relationEmpty ? null : JSON.stringify(nextFilters),
    };
    if (rowId) {
      await updateSettings({ id: rowId, model_name: model, ...payload });
    } else {
      const res = await createSettings({ model_name: model, ...payload })
        .unwrap()
        .catch(() => null);
      if (res?.id) setLocalRowId(res.id);
    }
  }, [
    draft,
    draftWidgets,
    draftFilters,
    serverCols,
    serverWidgets,
    serverFilters,
    defaultVisible,
    rowId,
    model,
    createSettings,
    updateSettings,
    deleteSettings,
  ]);

  const reset = useCallback(async () => {
    dirtyRef.current = false;
    setDraftState(defaultVisible); // мгновенно вернуть дефолтные колонки
    setDraftWidgets({});
    setDraftFilters({});
    const id = rowId;
    setLocalRowId(undefined);
    if (id) await deleteSettings({ id, model_name: model });
  }, [defaultVisible, rowId, model, deleteSettings]);

  return {
    selected,
    widgets,
    filters,
    isCustom,
    isLoading,
    setDraft,
    setWidget,
    setFilter,
    persistIfDirty,
    reset,
  };
}
