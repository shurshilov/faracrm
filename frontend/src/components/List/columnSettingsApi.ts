/**
 * API для пользовательских настроек колонок списков и полей карточек
 * канбана (per-user, per-model, per-view).
 *
 * Одна запись column_settings = набор видимых полей конкретного
 * пользователя для конкретной модели и вида (list — колонки списка,
 * kanban — поля карточки). Правила доступа на бэке отдают только СВОИ
 * строки, поэтому поиск по model_name и view_type всегда возвращает
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

/** Вид, к которому относится настройка. */
export type ColumnSettingsView = 'list' | 'kanban';

export interface ColumnSettingDTO {
  id: number;
  model_name: string;
  view_type: ColumnSettingsView;
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

/** Ключ настройки: модель + вид. */
export interface ColumnSettingKey {
  model_name: string;
  view_type: ColumnSettingsView;
}

export type RelationColumnWidgets = Record<string, RelationColumnWidget>;
export type RelationColumnFilters = Record<string, FilterExpression>;

const tag = ({ model_name, view_type }: ColumnSettingKey) => ({
  type: 'ColumnSettings',
  id: `${model_name}:${view_type}`,
});

const columnSettingsApi = crudApi.injectEndpoints({
  endpoints: build => ({
    // Получить настройку текущего пользователя для модели и вида.
    // Возвращает одну запись (или null, если пользователь не настраивал).
    getColumnSettings: build.query<ColumnSettingDTO | null, ColumnSettingKey>({
      query: ({ model_name, view_type }) => ({
        url: '/auto/column_settings/search',
        method: 'POST',
        body: {
          fields: [
            'id',
            'model_name',
            'view_type',
            'columns',
            'widgets',
            'filters',
          ],
          filter: [
            ['model_name', '=', model_name],
            ['view_type', '=', view_type],
          ],
          limit: 1,
        },
      }),
      transformResponse: (response: { data: ColumnSettingDTO[] }) =>
        response.data?.[0] ?? null,
      providesTags: (_result, _error, key) => [tag(key)],
    }),

    // Создать настройку (user_id проставит бэк дефолтом из сессии).
    createColumnSettings: build.mutation<
      { id: number },
      ColumnSettingKey & ColumnSettingPayload
    >({
      query: data => ({
        url: '/auto/column_settings',
        method: 'POST',
        body: data,
      }),
      invalidatesTags: (_result, _error, key) => [tag(key)],
    }),

    // Обновить существующую настройку.
    updateColumnSettings: build.mutation<
      void,
      { id: number } & ColumnSettingKey & ColumnSettingPayload
    >({
      query: ({ id, columns, widgets, filters }) => ({
        url: `/auto/column_settings/${id}`,
        method: 'PUT',
        body: { columns, widgets, filters },
      }),
      invalidatesTags: (_result, _error, key) => [tag(key)],
    }),

    // Удалить настройку (сброс к полям вью по умолчанию).
    deleteColumnSettings: build.mutation<
      void,
      { id: number } & ColumnSettingKey
    >({
      query: ({ id }) => ({
        url: `/auto/column_settings/${id}`,
        method: 'DELETE',
      }),
      invalidatesTags: (_result, _error, key) => [tag(key)],
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
