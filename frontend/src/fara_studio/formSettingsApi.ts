/**
 * API общих настроек форм (form_settings): одна запись на модель — какие
 * поля обязательны и зона «Дополнительно» (поля вне разметки, её место и
 * сетка).
 *
 * Таблица маленькая и нужна каждой форме, поэтому читается целиком один
 * раз при старте (FormSettingsPreloader), а формы берут свою модель из
 * кеша (useFormSettings). Пишет администратор настроек — ACL system_admin
 * на бэке.
 */
import { crudApi } from '@/services/api/crudApi';
import type { ExtraPlacement } from './zone/zoneGrid';

export interface FormSettingDTO {
  id: number;
  model_name: string;
  /** JSON-массив имён обязательных полей. */
  required: string | null;
  /** JSON-массив клеток зоны: {name, x, y, w, h}. */
  extra_fields: string | null;
  extra_placement: ExtraPlacement | null;
  extra_columns: number | null;
  /** null — строк сколько понадобится. */
  extra_rows: number | null;
}

/** Что меняем; остальные поля строки остаются как есть. */
export type FormSettingPatch = Partial<
  Omit<FormSettingDTO, 'id' | 'model_name'>
>;

const formSettingsApi = crudApi.injectEndpoints({
  endpoints: build => ({
    // Все настройки форм разом — по записи на модель.
    getFormSettings: build.query<FormSettingDTO[], void>({
      query: () => ({
        url: '/auto/form_settings/search',
        method: 'POST',
        body: {
          fields: [
            'id',
            'model_name',
            'required',
            'extra_fields',
            'extra_placement',
            'extra_columns',
            'extra_rows',
          ],
          limit: 200,
        },
      }),
      transformResponse: (response: { data: FormSettingDTO[] }) =>
        response.data,
      providesTags: [{ type: 'FormSettings', id: 'LIST' }],
      // Фоновый прогрев: роли без прав на form_settings работают без
      // настроек, модалки отказа не нужно.
      extraOptions: { silent: true },
    }),

    createFormSettings: build.mutation<
      { id: number },
      { model_name: string } & FormSettingPatch
    >({
      query: data => ({
        url: '/auto/form_settings',
        method: 'POST',
        body: data,
      }),
      invalidatesTags: [{ type: 'FormSettings', id: 'LIST' }],
    }),

    updateFormSettings: build.mutation<void, { id: number } & FormSettingPatch>(
      {
        query: ({ id, ...data }) => ({
          url: `/auto/form_settings/${id}`,
          method: 'PUT',
          body: data,
        }),
        invalidatesTags: [{ type: 'FormSettings', id: 'LIST' }],
      },
    ),
  }),
  overrideExisting: false,
});

export const {
  useGetFormSettingsQuery,
  useCreateFormSettingsMutation,
  useUpdateFormSettingsMutation,
} = formSettingsApi;
