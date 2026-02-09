/**
 * sessions.ts — custom hooks + types (unused codegen CRUD hooks removed)
 */
import { crudApi as api } from './crudApi';

const injectedRtkApi = api.injectEndpoints({
  endpoints: build => ({
    routeSessionsTerminateAll: build.mutation<
      TerminateAllResponse,
      TerminateAllArgs | void
    >({
      query: (queryArg) => ({
        url: `/sessions/terminate_all`,
        method: 'POST',
        params: {
          exclude_current: queryArg?.excludeCurrent ?? true,
        },
      }),
      invalidatesTags: ['sessions'],
    }),
  }),
  overrideExisting: false,
});

// Types
export type SchemaSession = {
  id: number;
  user_id?: any;
  token?: string | null;
  ip_address?: string | null;
  user_agent?: string | null;
  created_at?: string | null;
  expires_at?: string | null;
};

export type Session = SchemaSession;

export type SchemaModel = {
  id: number;
  name?: string | null;
  model?: string | null;
};

type TerminateAllArgs = {
  excludeCurrent?: boolean;
};

type TerminateAllResponse = {
  terminated_count: number;
};

export const {
  useRouteSessionsTerminateAllMutation,
} = injectedRtkApi;
