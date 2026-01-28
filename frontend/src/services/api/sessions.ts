import { crudApi as api } from './crudApi';
const injectedRtkApi = api.injectEndpoints({
  endpoints: build => ({
    routeSessionsTerminateAll: build.mutation<
      RouteSessionsTerminateAllApiResponse,
      RouteSessionsTerminateAllApiArg
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
    routeSessionsSearchPost: build.mutation<
      RouteSessionsSearchPostApiResponse,
      RouteSessionsSearchPostApiArg
    >({
      query: queryArg => ({
        url: `/sessions/search`,
        method: 'POST',
        body: queryArg.sessionSearchInput,
      }),
    }),
    routeSessionsSearchMany2ManyGet: build.query<
      RouteSessionsSearchMany2ManyGetApiResponse,
      RouteSessionsSearchMany2ManyGetApiArg
    >({
      query: queryArg => ({
        url: `/sessions/search_many2many`,
        params: {
          id: queryArg.id,
          name: queryArg.name,
          fields: queryArg.fields,
          order: queryArg.order,
          start: queryArg.start,
          end: queryArg.end,
          sort: queryArg.sort,
          limit: queryArg.limit,
        },
      }),
    }),
    routeSessionsPost: build.mutation<
      RouteSessionsPostApiResponse,
      RouteSessionsPostApiArg
    >({
      query: queryArg => ({
        url: `/sessions`,
        method: 'POST',
        body: queryArg.sessionCreate,
      }),
    }),
    routeSessionsDefaultValuesPost: build.mutation<
      RouteSessionsDefaultValuesPostApiResponse,
      RouteSessionsDefaultValuesPostApiArg
    >({
      query: queryArg => ({
        url: `/sessions/default_values`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput27,
      }),
    }),
    routeSessionsIdPut: build.mutation<
      RouteSessionsIdPutApiResponse,
      RouteSessionsIdPutApiArg
    >({
      query: queryArg => ({
        url: `/sessions/${queryArg.id}`,
        method: 'PUT',
        body: queryArg.sessionUpdate,
      }),
    }),
    routeSessionsIdDelete: build.mutation<
      RouteSessionsIdDeleteApiResponse,
      RouteSessionsIdDeleteApiArg
    >({
      query: queryArg => ({
        url: `/sessions/${queryArg.id}`,
        method: 'DELETE',
      }),
    }),
    routeSessionsIdPost: build.mutation<
      RouteSessionsIdPostApiResponse,
      RouteSessionsIdPostApiArg
    >({
      query: queryArg => ({
        url: `/sessions/${queryArg.id}`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput28,
      }),
    }),
    routeSessionsBulkDelete: build.mutation<
      RouteSessionsBulkDeleteApiResponse,
      RouteSessionsBulkDeleteApiArg
    >({
      query: queryArg => ({
        url: `/sessions/bulk`,
        method: 'DELETE',
        body: queryArg.ids,
      }),
    }),
  }),
  overrideExisting: false,
});
export { injectedRtkApi as crudApi };
export type RouteSessionsTerminateAllApiResponse = {
  terminated_count: number;
  message: string;
};
export type RouteSessionsTerminateAllApiArg = {
  excludeCurrent?: boolean;
};
export type RouteSessionsSearchPostApiResponse =
  /** status 200 успешно */ SchemaSearchOutputListSessionReadSearchOutput;
export type RouteSessionsSearchPostApiArg = {
  sessionSearchInput: SessionSearchInput;
};
export type RouteSessionsSearchMany2ManyGetApiResponse =
  /** status 200 успешно */ any;
export type RouteSessionsSearchMany2ManyGetApiArg = {
  id: number;
  name: null;
  fields: string[];
  order?: 'desc' | 'asc';
  start?: number | null;
  end?: number | null;
  sort?: string;
  limit?: number;
};
export type RouteSessionsPostApiResponse =
  /** status 200 успешно */ SchemaCreateOutput;
export type RouteSessionsPostApiArg = {
  sessionCreate: SessionCreate;
};
export type RouteSessionsDefaultValuesPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputSession;
export type RouteSessionsDefaultValuesPostApiArg = {
  backendBaseSystemDotormDotormUtilsSchemaGetInput27: SchemaGetInput;
};
export type RouteSessionsIdPutApiResponse =
  /** status 200 успешно */ SessionUpdate;
export type RouteSessionsIdPutApiArg = {
  id: number;
  sessionUpdate: SessionUpdate;
};
export type RouteSessionsIdDeleteApiResponse = /** status 200 успешно */ true;
export type RouteSessionsIdDeleteApiArg = {
  id: number;
};
export type RouteSessionsIdPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputSession;
export type RouteSessionsIdPostApiArg = {
  id: number;
  backendBaseSystemDotormDotormUtilsSchemaGetInput28: SchemaGetInput2;
};
export type RouteSessionsBulkDeleteApiResponse = /** status 200 успешно */ true;
export type RouteSessionsBulkDeleteApiArg = {
  ids: number[];
};
export type SchemaRelationNested = {
  id: number;
  name: string;
};
export type SessionReadSearchOutput = {
  id?: number | null;
  active?: boolean | null;
  user_id?: SchemaRelationNested | null;
  token?: string | null;
  ttl?: number | null;
  expired_datetime?: string | null;
  create_datetime?: string | null;
  create_user_id?: SchemaRelationNested | null;
  update_datetime?: string | null;
  update_user_id?: SchemaRelationNested | null;
};
export type SchemaSession = SessionReadSearchOutput;
export type GetListField = {
  name: string;
  type: string;
  relation?: string | null;
};
export type SchemaSearchOutputListSessionReadSearchOutput = {
  data: SessionReadSearchOutput[];
  total?: number | null;
  fields: GetListField[];
};
export type SessionSearchInput = {
  fields: (
    | 'id'
    | 'active'
    | 'user_id'
    | 'token'
    | 'ttl'
    | 'expired_datetime'
    | 'create_datetime'
    | 'create_user_id'
    | 'update_datetime'
    | 'update_user_id'
  )[];
  end?: number | null;
  order?: 'DESC' | 'ASC' | 'desc' | 'asc';
  sort?:
    | 'id'
    | 'active'
    | 'user_id'
    | 'token'
    | 'ttl'
    | 'expired_datetime'
    | 'create_datetime'
    | 'create_user_id'
    | 'update_datetime'
    | 'update_user_id';
  start?: number | null;
  limit?: number;
  filter?: (
    | ['id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['active', '=' | '!=', boolean]
    | ['user_id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | [
        'token',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | ['ttl', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['expired_datetime', '=' | '>' | '<' | '!=' | '>=' | '<=', string | null]
    | ['create_datetime', '=' | '>' | '<' | '!=' | '>=' | '<=', string]
    | ['create_user_id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['update_datetime', '=' | '>' | '<' | '!=' | '>=' | '<=', string]
    | ['update_user_id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
  )[];
  raw?: boolean;
};
export type SchemaCreateOutput = {
  id: number;
};
export type SessionCreate = {
  active?: boolean;
  user_id: number | 'VirtualId';
  token: string;
  ttl: number;
  expired_datetime: string | null;
  create_datetime?: string;
  create_user_id: number | 'VirtualId';
  update_datetime?: string;
  update_user_id: number | 'VirtualId';
};
export type SchemaUserNestedPartial = {
  id?: number | null;
  name?: string | null;
  login?: string | null;
  email?: string | null;
  password_hash?: string | null;
  password_salt?: string | null;
  image?: SchemaRelationNested | null;
  image_ids?: SchemaRelationNested[] | null;
  role_ids?: SchemaRelationNested[] | null;
};
export type Session = {
  id: number;
  active?: boolean;
  user_id: SchemaUserNestedPartial;
  token: string;
  ttl: number;
  expired_datetime: string | null;
  create_datetime?: string;
  create_user_id: SchemaUserNestedPartial;
  update_datetime?: string;
  update_user_id: SchemaUserNestedPartial;
};
export type GetFormField = {
  name: string;
  type: string;
  relatedModel?: string | null;
  relatedField?: string | null;
  options?: any[] | null;
};
export type SchemaGetOutputSession = {
  data: Session;
  fields: {
    [key: string]: GetFormField;
  };
};
export type SchemaGetInput = {
  fields: (
    | 'id'
    | 'active'
    | 'user_id'
    | 'token'
    | 'ttl'
    | 'expired_datetime'
    | 'create_datetime'
    | 'create_user_id'
    | 'update_datetime'
    | 'update_user_id'
  )[];
};
export type SessionUpdate = {
  active?: boolean | null;
  user_id?: number | 'VirtualId' | null;
  token?: string | null;
  ttl?: number | null;
  expired_datetime?: string | null;
  create_datetime?: string | null;
  create_user_id?: number | 'VirtualId' | null;
  update_datetime?: string | null;
  update_user_id?: number | 'VirtualId' | null;
};
export type SchemaGetInput2 = {
  fields: (
    | 'id'
    | 'active'
    | 'user_id'
    | 'token'
    | 'ttl'
    | 'expired_datetime'
    | 'create_datetime'
    | 'create_user_id'
    | 'update_datetime'
    | 'update_user_id'
  )[];
};
export const {
  useRouteSessionsTerminateAllMutation,
  useRouteSessionsSearchPostMutation,
  useRouteSessionsSearchMany2ManyGetQuery,
  useLazyRouteSessionsSearchMany2ManyGetQuery,
  useRouteSessionsPostMutation,
  useRouteSessionsDefaultValuesPostMutation,
  useRouteSessionsIdPutMutation,
  useRouteSessionsIdDeleteMutation,
  useRouteSessionsIdPostMutation,
  useRouteSessionsBulkDeleteMutation,
} = injectedRtkApi;
