/**
 * API студии — поля модели, добавленные из интерфейса (бэкенд
 * backend/base/system/studio, роуты /studio/fields). Только
 * администратору настроек.
 *
 * После изменения поле появляется (меняется, исчезает) в метаданных
 * модели — сбрасываем кеш полей (Fields), общих настроек формы
 * (FormSettings: новое поле бэк кладёт в «Дополнительно») и списков
 * модели.
 */
import { crudApi } from '@/services/api/crudApi';

export type StudioFieldType =
  | 'char'
  | 'text'
  | 'integer'
  | 'float'
  | 'boolean'
  | 'date'
  | 'datetime'
  | 'selection'
  | 'many2one';

export const STUDIO_FIELD_TYPES: StudioFieldType[] = [
  'char',
  'text',
  'integer',
  'float',
  'boolean',
  'date',
  'datetime',
  'selection',
  'many2one',
];

export interface StudioFieldDTO {
  id: number;
  model_name: string;
  name: string;
  label: string;
  field_type: StudioFieldType;
  /** Пары [значение, подпись] — у выбора из списка. */
  options: [string, string][] | null;
  /** Таблица связанной модели — у ссылки на запись. */
  relation_model: string | null;
}

export type StudioFieldCreate = Omit<StudioFieldDTO, 'id'>;

export interface StudioFieldUpdate {
  id: number;
  model_name: string;
  label?: string;
  options?: [string, string][];
}

const changedTags = (model: string) => [
  { type: 'StudioFields', id: model },
  { type: 'Fields', id: model },
  { type: 'FormSettings', id: 'LIST' },
  { type: model, id: 'LIST' },
];

const studioApi = crudApi.injectEndpoints({
  endpoints: build => ({
    getStudioFields: build.query<StudioFieldDTO[], string>({
      query: model => ({ url: `/studio/fields/${model}`, method: 'GET' }),
      providesTags: (_result, _error, model) => [
        { type: 'StudioFields', id: model },
      ],
    }),

    createStudioField: build.mutation<{ id: number }, StudioFieldCreate>({
      query: data => ({ url: '/studio/fields', method: 'POST', body: data }),
      invalidatesTags: (_result, _error, data) => changedTags(data.model_name),
    }),

    // Подпись и варианты; имя и тип не меняются.
    updateStudioField: build.mutation<StudioFieldDTO, StudioFieldUpdate>({
      query: ({ id, label, options }) => ({
        url: `/studio/fields/${id}`,
        method: 'PATCH',
        body: { label, options },
      }),
      invalidatesTags: (_result, _error, { model_name }) => [
        { type: 'StudioFields', id: model_name },
        { type: 'Fields', id: model_name },
      ],
    }),

    deleteStudioField: build.mutation<
      boolean,
      { id: number; model_name: string }
    >({
      query: ({ id }) => ({ url: `/studio/fields/${id}`, method: 'DELETE' }),
      invalidatesTags: (_result, _error, { model_name }) =>
        changedTags(model_name),
    }),
  }),
  overrideExisting: false,
});

export const {
  useGetStudioFieldsQuery,
  useCreateStudioFieldMutation,
  useUpdateStudioFieldMutation,
  useDeleteStudioFieldMutation,
} = studioApi;
