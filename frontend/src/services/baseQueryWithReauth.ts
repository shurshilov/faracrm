import { fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import type {
  BaseQueryFn,
  FetchArgs,
  FetchBaseQueryError,
} from '@reduxjs/toolkit/query';
import type { RootState } from '@store/store';
import queryString from 'query-string';
import { logOut } from '@/slices/authSlice';
import { apiErrorEmitter, ApiError } from '@/components/ErrorModal';

export const API_BASE_URL = 'http://127.0.0.1:8090';

export const baseQuery = fetchBaseQuery({
  baseUrl: `${API_BASE_URL}/`,
  prepareHeaders: (headers, { getState }) => {
    const token = (getState() as RootState).auth.session?.token;
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }
    headers.set('Content-Type', 'application/json');
    headers.set('Accept', 'application/json');
    return headers;
  },
  paramsSerializer: params => queryString.stringify(params, { encode: false }),
});

// Коды ошибок авторизации - при них делаем logout
const AUTH_ERROR_CODES = [
  'TOKEN_EXPIRED',
  'TOKEN_INVALID',
  'SESSION_EXPIRED',
  'SESSION_NOT_EXIST',
  'UNAUTHORIZED',
];

function isAuthError(data: unknown): boolean {
  if (typeof data === 'string') {
    return AUTH_ERROR_CODES.includes(data);
  }
  if (typeof data === 'object' && data !== null) {
    const content = (data as { content?: string }).content;
    if (content && AUTH_ERROR_CODES.includes(content)) {
      return true;
    }
  }
  return false;
}

function parseApiError(data: unknown, status: number): ApiError | null {
  // Если data - строка (старый формат)
  if (typeof data === 'string') {
    return {
      content: data,
      status_code: status,
    };
  }

  // Если data - объект с полем content
  if (typeof data === 'object' && data !== null) {
    const obj = data as Record<string, unknown>;
    if (obj.content && typeof obj.content === 'string') {
      return {
        content: obj.content,
        detail: obj.detail as string | undefined,
        status_code: status,
      };
    }
  }

  return null;
}

export const baseQueryWithReauth: BaseQueryFn<
  string | FetchArgs,
  unknown,
  FetchBaseQueryError
> = async (args, api, extraOptions) => {
  const result = await baseQuery(args, api, extraOptions);

  if (result.error) {
    const status = result.error.status;
    const data = result.error.data;

    // 401 - всегда logout
    if (status === 401) {
      api.dispatch(logOut());
      return result;
    }

    // 403 - проверяем тип ошибки
    if (status === 403) {
      // Ошибка авторизации - logout
      if (isAuthError(data)) {
        api.dispatch(logOut());
        return result;
      }

      // Ошибка прав - показываем модальное окно
      const apiError = parseApiError(data, status as number);
      if (apiError) {
        apiErrorEmitter.emit(apiError);
      }
    }

    // 404 - показываем модальное окно
    if (status === 404) {
      const apiError = parseApiError(data, status as number);
      if (apiError) {
        apiErrorEmitter.emit(apiError);
      }
    }

    // 422 - ошибка валидации
    if (status === 422) {
      const validationData = data as { detail?: unknown };
      apiErrorEmitter.emit({
        content: 'VALIDATION_ERROR',
        detail: validationData?.detail as any,
        status_code: 422,
      });
    }
  }

  return result;
};
