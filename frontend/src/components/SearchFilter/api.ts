/**
 * API для компонента SearchFilter
 */
import { crudApi } from '@/services/api/crudApi';

export interface FieldInfoResponse {
  name: string;
  type: string;
  relation?: string;
  options?: string[];
  required?: boolean;
}

// Расширяем crudApi
const searchFilterApi = crudApi.injectEndpoints({
  endpoints: build => ({
    // Получение списка полей модели для фильтрации
    getFields: build.query<FieldInfoResponse[], string>({
      query: model => ({
        url: `/${model}/fields`,
        method: 'GET',
      }),
      // Кэшируем на уровне модели
      providesTags: (result, error, model) => [{ type: 'Fields', id: model }],
    }),
  }),
  overrideExisting: false,
});

export const { useGetFieldsQuery } = searchFilterApi;
