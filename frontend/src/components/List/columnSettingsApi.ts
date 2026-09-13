/**
 * API для пользовательских настроек колонок списков (per-user, per-model).
 *
 * Одна запись column_settings = набор видимых колонок конкретного
 * пользователя для конкретной модели. Правила доступа на бэке отдают
 * только СВОИ строки, поэтому поиск по model_name всегда возвращает
 * настройку текущего пользователя (или ничего).
 *
 * У колонок-связей (One2many/Many2many/полиморфные) есть свои настройки:
 * widgets — как рисовать, filters — фильтр на связанные записи (формат
 * триплетов фильтра списков). На сервере — JSON-словари по имени поля.
 */
import { crudApi } from '@/services/api/crudApi';
import type { FilterExpression } from '@/services/api/crudTypes';

/** Как рисовать колонку-связь. */
export type RelationColumnWidget = 'count' | 'present' | 'text';

export interface ColumnSettingDTO {
  id: number;
  model_name: string;
  /** JSON-массив имён полей в порядке отображения. */
  columns: string;
  /** JSON {имя поля: RelationColumnWidget}. */
  widgets?: string | null;
  /** JSON {имя поля: FilterExpression}. */
  filters?: string | null;
}

export interface ColumnSettingPayload {
  columns: string;
  widgets?: string | null;
  filters?: string | null;
}

export type RelationColumnWidgets = Record<string, RelationColumnWidget>;
export type RelationColumnFilters = Record<string, FilterExpression>;

const columnSettingsApi = crudApi.injectEndpoints({
  endpoints: build => ({
    // Получить настройку колонок текущего пользователя для модели.
    // Возвращает одну запись (или null, если пользователь не настраивал).
    getColumnSettings: build.query<ColumnSettingDTO | null, string>({
      query: modelName => ({
        url: '/auto/column_settings/search',
        method: 'POST',
        body: {
          fields: ['id', 'model_name', 'columns', 'widgets', 'filters'],
          filter: [['model_name', '=', modelName]],
          limit: 1,
        },
      }),
      transformResponse: (response: { data: ColumnSettingDTO[] }) =>
        response.data?.[0] ?? null,
      providesTags: (_result, _error, modelName) => [
        { type: 'ColumnSettings', id: modelName },
      ],
    }),

    // Создать настройку колонок (user_id проставит бэк дефолтом из сессии).
    createColumnSettings: build.mutation<
      { id: number },
      { model_name: string } & ColumnSettingPayload
    >({
      query: data => ({
        url: '/auto/column_settings',
        method: 'POST',
        body: data,
      }),
      invalidatesTags: (_result, _error, data) => [
        { type: 'ColumnSettings', id: data.model_name },
      ],
    }),

    // Обновить существующую настройку.
    updateColumnSettings: build.mutation<
      void,
      { id: number; model_name: string } & ColumnSettingPayload
    >({
      query: ({ id, columns, widgets, filters }) => ({
        url: `/auto/column_settings/${id}`,
        method: 'PUT',
        body: { columns, widgets, filters },
      }),
      invalidatesTags: (_result, _error, { model_name }) => [
        { type: 'ColumnSettings', id: model_name },
      ],
    }),

    // Удалить настройку (сброс к колонкам вью по умолчанию).
    deleteColumnSettings: build.mutation<
      void,
      { id: number; model_name: string }
    >({
      query: ({ id }) => ({
        url: `/auto/column_settings/${id}`,
        method: 'DELETE',
      }),
      invalidatesTags: (_result, _error, { model_name }) => [
        { type: 'ColumnSettings', id: model_name },
      ],
    }),
  }),
  overrideExisting: false,
});

export const {
  useGetColumnSettingsQuery,
  useCreateColumnSettingsMutation,
  useUpdateColumnSettingsMutation,
  useDeleteColumnSettingsMutation,
} = columnSettingsApi;
