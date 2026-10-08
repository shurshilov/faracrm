/**
 * useStudioEditor — состояние и действия редактора зоны «Дополнительно»
 * в режиме студии: поля зоны по клеткам сетки, её место и размер,
 * обязательность (общие настройки формы, form_settings) плюс поля студии
 * (studio_fields).
 *
 * Каждое действие пишется на сервер сразу, как в Odoo Studio; черновик
 * держим локально, чтобы перетаскивание не мигало до ответа. Редактор
 * один на форму (StudioFormShell) и доходит до зоны через
 * StudioEditorContext, где бы зона ни стояла.
 */
import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { useTranslation } from 'react-i18next';
import { useGetFieldsQuery, FieldInfoResponse } from '@/services/api/crudApi';
import {
  FormSettingPatch,
  useCreateFormSettingsMutation,
  useGetFormSettingsQuery,
  useUpdateFormSettingsMutation,
} from './formSettingsApi';
import {
  ExtraCell,
  ExtraGridSize,
  ExtraPlacement,
  StoredCell,
  placeAt,
  placeCells,
  resizeCell,
} from './zone/zoneGrid';
import { extraCells, useFormSettings } from './useFormSettings';
import { fieldLabel } from '@/components/Form/fieldLabel';
import {
  StudioFieldDTO,
  StudioFieldType,
  useCreateStudioFieldMutation,
  useDeleteStudioFieldMutation,
  useGetStudioFieldsQuery,
  useUpdateStudioFieldMutation,
} from './api';

export interface StudioEditor {
  /** Поля зоны на своих местах в сетке. */
  cells: ExtraCell[];
  grid: ExtraGridSize;
  placement: ExtraPlacement;
  /** Обязательные поля из общих настроек формы. */
  required: string[];
  selected: string | null;
  saving: boolean;
  studioRows: StudioFieldDTO[];
  allFields: FieldInfoResponse[];
  label: (name: string) => string;
  select: (name: string | null) => void;
  /** Можно ли поставить поле (null — новое) в клетку. */
  canPlace: (name: string | null, x: number, y: number) => boolean;
  place: (name: string, x: number, y: number) => Promise<void>;
  addNew: (
    type: StudioFieldType,
    x: number,
    y: number,
    relation?: string,
  ) => Promise<void>;
  resize: (name: string, w: number, h: number) => Promise<void>;
  setGrid: (grid: ExtraGridSize) => Promise<void>;
  setPlacement: (placement: ExtraPlacement) => Promise<void>;
  removeFromForm: (name: string) => Promise<void>;
  setRequired: (name: string, on: boolean) => Promise<void>;
  setLabel: (id: number, label: string) => Promise<void>;
  setOptions: (id: number, options: [string, string][]) => Promise<void>;
  deleteField: (id: number) => Promise<void>;
}

export const StudioEditorContext = createContext<StudioEditor | null>(null);

interface Draft {
  cells: StoredCell[];
  required: string[];
  grid: ExtraGridSize;
  placement: ExtraPlacement;
}

export function useStudioEditor(
  model: string,
  layoutFields: string[],
): StudioEditor {
  const { t } = useTranslation(['studio', 'common']);
  const settings = useFormSettings(model);
  const { refetch: refetchSettings } = useGetFormSettingsQuery();
  const { data: studioRows } = useGetStudioFieldsQuery(model);
  const { data: allFields } = useGetFieldsQuery(model);
  const [createSettings] = useCreateFormSettingsMutation();
  const [updateSettings] = useUpdateFormSettingsMutation();
  const [createField] = useCreateStudioFieldMutation();
  const [updateField] = useUpdateStudioFieldMutation();
  const [deleteFieldRow] = useDeleteStudioFieldMutation();

  const server = useMemo<Draft>(
    () => ({
      cells: settings.cells,
      required: settings.required,
      grid: settings.grid,
      placement: settings.placement,
    }),
    [settings],
  );
  const [draft, setDraft] = useState(server);
  const [selected, setSelected] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => setDraft(server), [server]);

  // Как у формы: поля вне разметки плюс обязательные, по сетке.
  const cells = useMemo(
    () =>
      placeCells(
        extraCells(draft.cells, draft.required, layoutFields),
        draft.grid,
      ),
    [draft, layoutFields],
  );

  // Запись общих настроек формы: по строке из кеша, а если её ещё нет —
  // создание. Бэк проверяет имена и сетку (@constrains form_setting).
  const save = useCallback(
    async (patch: FormSettingPatch) => {
      setSaving(true);
      try {
        if (settings.row) {
          await updateSettings({ id: settings.row.id, ...patch }).unwrap();
        } else {
          await createSettings({ model_name: model, ...patch }).unwrap();
        }
      } finally {
        setSaving(false);
      }
    },
    [settings.row, model, updateSettings, createSettings],
  );

  const saveCells = useCallback(
    (next: ExtraCell[]) => {
      setDraft(prev => ({ ...prev, cells: next }));
      return save({ extra_fields: JSON.stringify(next) });
    },
    [save],
  );

  const label = useCallback(
    (name: string) => {
      const row = studioRows?.find(r => r.name === name);
      if (row) return row.label;
      const info = allFields?.find(f => f.name === name);
      return info ? fieldLabel(t, model, info) : name;
    },
    [studioRows, allFields, model, t],
  );

  const canPlace = useCallback(
    (name: string | null, x: number, y: number) =>
      placeAt(cells, name ?? '', x, y, draft.grid) !== null,
    [cells, draft.grid],
  );

  const place = useCallback(
    async (name: string, x: number, y: number) => {
      const next = placeAt(cells, name, x, y, draft.grid);
      if (!next) return;
      setSelected(name);
      await saveCells(next);
    },
    [cells, draft.grid, saveCells],
  );

  const addNew = useCallback(
    async (type: StudioFieldType, x: number, y: number, relation?: string) => {
      // Имя — свободное x_<тип>_<номер>, как x_studio_… в Odoo.
      const taken = new Set([
        ...(allFields ?? []).map(f => f.name),
        ...(studioRows ?? []).map(r => r.name),
      ]);
      let n = 1;
      while (taken.has(`x_${type}_${n}`)) n += 1;
      const name = `x_${type}_${n}`;

      setSaving(true);
      try {
        await createField({
          model_name: model,
          name,
          label: t('newLabel'),
          field_type: type,
          options:
            type === 'selection' ? [['option_1', `${t('option')} 1`]] : null,
          relation_model: relation ?? null,
        }).unwrap();
        // Бэк дописал поле в зону без места (и завёл строку настроек,
        // если её не было) — ставим в клетку броска; занята — в свободную.
        const rows = await refetchSettings().unwrap();
        const fresh = rows.find(r => r.model_name === model);
        const next =
          placeAt(cells, name, x, y, draft.grid) ??
          placeCells([...cells, { name }], draft.grid);
        setDraft(prev => ({ ...prev, cells: next }));
        setSelected(name);
        if (fresh) {
          await updateSettings({
            id: fresh.id,
            extra_fields: JSON.stringify(next),
          }).unwrap();
        }
      } finally {
        setSaving(false);
      }
    },
    [
      allFields,
      studioRows,
      model,
      t,
      createField,
      refetchSettings,
      cells,
      draft.grid,
      updateSettings,
    ],
  );

  const resize = useCallback(
    async (name: string, w: number, h: number) => {
      const next = resizeCell(cells, name, w, h, draft.grid);
      if (next) await saveCells(next);
    },
    [cells, draft.grid, saveCells],
  );

  // Сохранённые места не трогаем: уменьшили сетку — не влезшие поля
  // встают в свободные клетки (placeCells), вернули — на свои места.
  const setGrid = useCallback(
    async (grid: ExtraGridSize) => {
      setDraft(prev => ({ ...prev, grid }));
      await save({ extra_columns: grid.columns, extra_rows: grid.rows });
    },
    [save],
  );

  const setPlacement = useCallback(
    async (placement: ExtraPlacement) => {
      setDraft(prev => ({ ...prev, placement }));
      await save({ extra_placement: placement });
    },
    [save],
  );

  const removeFromForm = useCallback(
    async (name: string) => {
      const nextCells = cells.filter(cell => cell.name !== name);
      // Снятое с формы поле не может оставаться обязательным.
      const nextRequired = draft.required.filter(n => n !== name);
      setDraft(prev => ({ ...prev, cells: nextCells, required: nextRequired }));
      setSelected(prev => (prev === name ? null : prev));
      await save({
        extra_fields: JSON.stringify(nextCells),
        required: JSON.stringify(nextRequired),
      });
    },
    [cells, draft.required, save],
  );

  const setRequired = useCallback(
    async (name: string, on: boolean) => {
      const others = draft.required.filter(n => n !== name);
      const next = on ? [...others, name] : others;
      setDraft(prev => ({ ...prev, required: next }));
      await save({ required: JSON.stringify(next) });
    },
    [draft.required, save],
  );

  const setLabel = useCallback(
    async (id: number, label: string) => {
      setSaving(true);
      try {
        await updateField({ id, model_name: model, label }).unwrap();
      } finally {
        setSaving(false);
      }
    },
    [model, updateField],
  );

  const setOptions = useCallback(
    async (id: number, options: [string, string][]) => {
      setSaving(true);
      try {
        await updateField({ id, model_name: model, options }).unwrap();
      } finally {
        setSaving(false);
      }
    },
    [model, updateField],
  );

  const deleteField = useCallback(
    async (id: number) => {
      const name = studioRows?.find(r => r.id === id)?.name;
      setSaving(true);
      try {
        await deleteFieldRow({ id, model_name: model }).unwrap();
        // Бэк убрал имя из настроек формы (forget); локально — тоже.
        if (name) {
          setDraft(prev => ({
            ...prev,
            cells: prev.cells.filter(cell => cell.name !== name),
            required: prev.required.filter(n => n !== name),
          }));
          setSelected(prev => (prev === name ? null : prev));
        }
      } finally {
        setSaving(false);
      }
    },
    [studioRows, model, deleteFieldRow],
  );

  return {
    cells,
    grid: draft.grid,
    placement: draft.placement,
    required: draft.required,
    selected,
    saving,
    studioRows: studioRows ?? [],
    allFields: allFields ?? [],
    label,
    select: setSelected,
    canPlace,
    place,
    addNew,
    resize,
    setGrid,
    setPlacement,
    removeFromForm,
    setRequired,
    setLabel,
    setOptions,
    deleteField,
  };
}
