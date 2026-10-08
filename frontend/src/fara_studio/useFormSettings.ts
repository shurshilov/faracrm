/**
 * useFormSettings — общие настройки формы модели из прогретого кеша
 * (formSettingsApi): обязательные поля и зона «Дополнительно» — поля вне
 * разметки, её место и сетка. useZone — та же зона, разложенная по сетке
 * для конкретной формы (без полей её разметки).
 *
 * Без установленной студии настройки не грузятся и не применяются: её поля
 * (x_…) без неё не висят на моделях, и форма запросила бы неизвестные поля.
 * Строки в базе остаются — поставили студию снова, всё вернулось.
 */
import { useMemo } from 'react';
import { useAppInstalled } from '@/hooks/useInstalledApps';
import { FormSettingDTO, useGetFormSettingsQuery } from './formSettingsApi';
import {
  ExtraCell,
  ExtraGridSize,
  ExtraPlacement,
  StoredCell,
  parseCells,
  placeCells,
} from './zone/zoneGrid';

export interface FormSettings {
  /** Ответ получен (пусть и пустой или с ошибкой) — форму можно грузить. */
  ready: boolean;
  /** Запись модели на сервере; null — не настраивалась. */
  row: FormSettingDTO | null;
  required: string[];
  /** Клетки зоны «Дополнительно» как сохранены. */
  cells: StoredCell[];
  placement: ExtraPlacement;
  grid: ExtraGridSize;
}

/** Имена полей из JSON-массива настройки; битое значение — пусто. */
export function parseNames(raw: string | null | undefined): string[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed)
      ? parsed.filter((x): x is string => typeof x === 'string')
      : [];
  } catch {
    return [];
  }
}

/** Настройки форм нужны, только когда установлена студия. */
export function useFormSettingsEnabled(): boolean | undefined {
  return useAppInstalled('studio');
}

export function useFormSettings(model: string): FormSettings {
  const enabled = useFormSettingsEnabled();
  const { data, isSuccess, isError } = useGetFormSettingsQuery(undefined, {
    skip: !enabled,
  });
  return useMemo(() => {
    const row = data?.find(r => r.model_name === model) ?? null;
    return {
      // Без студии — сразу, со студией — когда пришёл ответ.
      ready: enabled === false || isSuccess || isError,
      row,
      required: parseNames(row?.required),
      cells: parseCells(row?.extra_fields),
      placement: row?.extra_placement ?? 'bottom',
      grid: {
        columns: row?.extra_columns || 1,
        rows: row?.extra_rows || null,
      },
    };
  }, [enabled, data, isSuccess, isError, model]);
}

/**
 * Клетки зоны «Дополнительно»: сохранённые поля, которых нет в разметке
 * формы (и расширениях), затем обязательные оттуда же — иначе
 * обязательное поле негде заполнить; без места, встанут в свободные
 * клетки.
 */
export function extraCells(
  cells: StoredCell[],
  required: string[],
  layoutFields: Iterable<string>,
): StoredCell[] {
  const known = new Set(layoutFields);
  const result = cells.filter(cell => !known.has(cell.name));
  for (const name of required) {
    if (!known.has(name) && !result.some(cell => cell.name === name)) {
      result.push({ name });
    }
  }
  return result;
}

export interface Zone {
  ready: boolean;
  /** Поля зоны на своих местах в сетке, по строкам. */
  cells: ExtraCell[];
  required: string[];
  placement: ExtraPlacement;
  grid: ExtraGridSize;
}

/** Зона «Дополнительно» формы: настройки модели без полей её разметки. */
export function useZone(model: string, layoutFields: string[]): Zone {
  const settings = useFormSettings(model);
  return useMemo(
    () => ({
      ready: settings.ready,
      cells: placeCells(
        extraCells(settings.cells, settings.required, layoutFields),
        settings.grid,
      ),
      required: settings.required,
      placement: settings.placement,
      grid: settings.grid,
    }),
    [settings, layoutFields],
  );
}
