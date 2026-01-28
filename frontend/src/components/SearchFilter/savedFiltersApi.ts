/**
 * API для сохранённых фильтров
 */
import { crudApi } from '@/services/api/crudApi';

export interface SavedFilterDTO {
  id: number;
  name: string;
  model_name: string;
  filter_data: string; // JSON string
  user_id?: number;
  is_global: boolean;
  is_default: boolean;
  created_at?: string;
  last_used_at?: string;
  use_count: number;
}

export interface CreateSavedFilterDTO {
  name: string;
  model_name: string;
  filter_data: string;
  is_global?: boolean;
  is_default?: boolean;
}

export interface UpdateSavedFilterDTO {
  name?: string;
  filter_data?: string;
  is_global?: boolean;
  is_default?: boolean;
}

// Расширяем crudApi для saved_filters
const savedFiltersApi = crudApi.injectEndpoints({
  endpoints: build => ({
    // Получить фильтры для модели (свои + глобальные)
    getSavedFilters: build.query<SavedFilterDTO[], string>({
      query: modelName => ({
        url: '/saved_filters/search',
        method: 'POST',
        body: {
          fields: [
            'id',
            'name',
            'model_name',
            'filter_data',
            'is_global',
            'is_default',
            'use_count',
            'last_used_at',
          ],
          filter: [['model_name', '=', modelName]],
          sort: 'use_count',
          order: 'desc',
          limit: 100,
        },
      }),
      transformResponse: (response: { data: SavedFilterDTO[] }) =>
        response.data,
      providesTags: (result, error, modelName) => [
        { type: 'SavedFilters', id: modelName },
        { type: 'SavedFilters', id: 'LIST' },
      ],
    }),

    // Создать сохранённый фильтр
    createSavedFilter: build.mutation<{ id: number }, CreateSavedFilterDTO>({
      query: data => ({
        url: '/saved_filters',
        method: 'POST',
        body: data,
      }),
      invalidatesTags: (result, error, data) => [
        { type: 'SavedFilters', id: data.model_name },
        { type: 'SavedFilters', id: 'LIST' },
      ],
    }),

    // Обновить фильтр
    updateSavedFilter: build.mutation<
      void,
      { id: number; data: UpdateSavedFilterDTO }
    >({
      query: ({ id, data }) => ({
        url: `/saved_filters/${id}`,
        method: 'PUT',
        body: data,
      }),
      invalidatesTags: [{ type: 'SavedFilters', id: 'LIST' }],
    }),

    // Удалить фильтр
    deleteSavedFilter: build.mutation<void, number>({
      query: id => ({
        url: `/saved_filters/${id}`,
        method: 'DELETE',
      }),
      invalidatesTags: [{ type: 'SavedFilters', id: 'LIST' }],
    }),

    // Отметить использование фильтра (увеличить счётчик)
    useSavedFilter: build.mutation<void, number>({
      query: id => ({
        url: `/saved_filters/${id}`,
        method: 'PUT',
        body: {
          use_count: 1, // Backend should increment
          last_used_at: new Date().toISOString(),
        },
      }),
      // Не инвалидируем кэш - это просто статистика
    }),
  }),
  overrideExisting: false,
});

export const {
  useGetSavedFiltersQuery,
  useCreateSavedFilterMutation,
  useUpdateSavedFilterMutation,
  useDeleteSavedFilterMutation,
  useUseSavedFilterMutation,
} = savedFiltersApi;
