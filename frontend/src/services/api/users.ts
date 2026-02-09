/**
 * users.ts — custom hooks + types (unused codegen CRUD hooks removed)
 */
import { crudApi as api } from './crudApi';

const injectedRtkApi = api.injectEndpoints({
  endpoints: build => ({
    routeUsersSearchPost: build.mutation<
      RouteUsersSearchPostApiResponse,
      RouteUsersSearchPostApiArg
    >({
      query: queryArg => ({
        url: `/users/search`,
        method: 'POST',
        body: queryArg.userSearchInput,
      }),
    }),
    changePassword: build.mutation<void, ChangePasswordArgs>({
      query: ({ userId, password }) => ({
        url: `/users/password_change`,
        method: 'POST',
        body: { user_id: userId, password },
      }),
    }),
    copyUser: build.mutation<CopyUserResponse, CopyUserArgs>({
      query: args => ({
        url: `/users/copy`,
        method: 'POST',
        body: args,
      }),
    }),
  }),
  overrideExisting: false,
});

// Types — canonical source: '@/types/records'
export { type UserRecord as SchemaUser } from '@/types/records';

export type ChangePasswordArgs = {
  userId: number;
  password: string;
};

export type CopyUserArgs = {
  source_user_id: number;
  name: string;
  login: string;
  copy_password: boolean;
  copy_roles: boolean;
  copy_files: boolean;
  copy_languages: boolean;
  copy_is_admin: boolean;
  copy_contacts: boolean;
};

export type CopyUserResponse = {
  id: number;
  name: string;
  login: string;
};

type UserSearchInput = {
  fields: string[];
  filter?: any[];
  start?: number | null;
  end?: number | null;
  limit?: number;
  order?: string;
  sort?: string;
  raw?: boolean;
};

type RouteUsersSearchPostApiResponse = {
  data: any[];
  total?: number | null;
  fields: any[];
};

type RouteUsersSearchPostApiArg = {
  userSearchInput: UserSearchInput;
};

export const {
  useRouteUsersSearchPostMutation,
  useChangePasswordMutation,
  useCopyUserMutation,
} = injectedRtkApi;
