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
      query: queryArg => ({
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

// Types — canonical source: '@/types/records'
export { type SessionRecord as SchemaSession } from '@/types/records';
export { type SessionRecord as Session } from '@/types/records';
export { type ModelRecord as SchemaModel } from '@/types/records';

type TerminateAllArgs = {
  excludeCurrent?: boolean;
};

type TerminateAllResponse = {
  terminated_count: number;
};

export const { useRouteSessionsTerminateAllMutation } = injectedRtkApi;
