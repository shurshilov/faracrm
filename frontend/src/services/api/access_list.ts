import { crudApi as api } from './crudApi';
const injectedRtkApi = api.injectEndpoints({
  endpoints: build => ({
    routeAccessListSearchPost: build.mutation<
      RouteAccessListSearchPostApiResponse,
      RouteAccessListSearchPostApiArg
    >({
      query: queryArg => ({
        url: `/access_list/search`,
        method: 'POST',
        body: queryArg.accessListSearchInput,
      }),
    }),
    routeAccessListSearchMany2ManyGet: build.query<
      RouteAccessListSearchMany2ManyGetApiResponse,
      RouteAccessListSearchMany2ManyGetApiArg
    >({
      query: queryArg => ({
        url: `/access_list/search_many2many`,
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
    routeAccessListPost: build.mutation<
      RouteAccessListPostApiResponse,
      RouteAccessListPostApiArg
    >({
      query: queryArg => ({
        url: `/access_list`,
        method: 'POST',
        body: queryArg.accessListCreate,
      }),
    }),
    routeAccessListDefaultValuesPost: build.mutation<
      RouteAccessListDefaultValuesPostApiResponse,
      RouteAccessListDefaultValuesPostApiArg
    >({
      query: queryArg => ({
        url: `/access_list/default_values`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput1,
      }),
    }),
    routeAccessListIdPut: build.mutation<
      RouteAccessListIdPutApiResponse,
      RouteAccessListIdPutApiArg
    >({
      query: queryArg => ({
        url: `/access_list/${queryArg.id}`,
        method: 'PUT',
        body: queryArg.accessListUpdate,
      }),
    }),
    routeAccessListIdDelete: build.mutation<
      RouteAccessListIdDeleteApiResponse,
      RouteAccessListIdDeleteApiArg
    >({
      query: queryArg => ({
        url: `/access_list/${queryArg.id}`,
        method: 'DELETE',
      }),
    }),
    routeAccessListIdPost: build.mutation<
      RouteAccessListIdPostApiResponse,
      RouteAccessListIdPostApiArg
    >({
      query: queryArg => ({
        url: `/access_list/${queryArg.id}`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput2,
      }),
    }),
    routeAccessListBulkDelete: build.mutation<
      RouteAccessListBulkDeleteApiResponse,
      RouteAccessListBulkDeleteApiArg
    >({
      query: queryArg => ({
        url: `/access_list/bulk`,
        method: 'DELETE',
        body: queryArg.ids,
      }),
    }),
  }),
  overrideExisting: false,
});
export { injectedRtkApi as crudApi };
export type RouteAccessListSearchPostApiResponse =
  /** status 200 успешно */ SchemaSearchOutputListAccessListReadSearchOutput;
export type RouteAccessListSearchPostApiArg = {
  accessListSearchInput: AccessListSearchInput;
};
export type RouteAccessListSearchMany2ManyGetApiResponse =
  /** status 200 успешно */ any;
export type RouteAccessListSearchMany2ManyGetApiArg = {
  id: number;
  name: null;
  fields: string[];
  order?: 'desc' | 'asc';
  start?: number | null;
  end?: number | null;
  sort?: string;
  limit?: number;
};
export type RouteAccessListPostApiResponse =
  /** status 200 успешно */ SchemaCreateOutput;
export type RouteAccessListPostApiArg = {
  accessListCreate: AccessListCreate;
};
export type RouteAccessListDefaultValuesPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputAccessList;
export type RouteAccessListDefaultValuesPostApiArg = {
  backendBaseSystemDotormDotormUtilsSchemaGetInput1: SchemaGetInput;
};
export type RouteAccessListIdPutApiResponse =
  /** status 200 успешно */ AccessListUpdate;
export type RouteAccessListIdPutApiArg = {
  id: number;
  accessListUpdate: AccessListUpdate;
};
export type RouteAccessListIdDeleteApiResponse = /** status 200 успешно */ true;
export type RouteAccessListIdDeleteApiArg = {
  id: number;
};
export type RouteAccessListIdPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputAccessList;
export type RouteAccessListIdPostApiArg = {
  id: number;
  backendBaseSystemDotormDotormUtilsSchemaGetInput2: SchemaGetInput2;
};
export type RouteAccessListBulkDeleteApiResponse =
  /** status 200 успешно */ true;
export type RouteAccessListBulkDeleteApiArg = {
  ids: number[];
};
export type SchemaRelationNested = {
  id: number;
  name: string;
};
export type AccessListReadSearchOutput = {
  id?: number | null;
  active?: boolean | null;
  name?: string | null;
  model_id?: SchemaRelationNested | null;
  role_id?: SchemaRelationNested | null;
  perm_create?: boolean | null;
  perm_read?: boolean | null;
  perm_update?: boolean | null;
  perm_delete?: boolean | null;
};
export type GetListField = {
  name: string;
  type: string;
  relation?: string | null;
};
export type SchemaSearchOutputListAccessListReadSearchOutput = {
  data: AccessListReadSearchOutput[];
  total?: number | null;
  fields: GetListField[];
};
export type AccessListSearchInput = {
  fields: (
    | 'id'
    | 'active'
    | 'name'
    | 'model_id'
    | 'role_id'
    | 'perm_create'
    | 'perm_read'
    | 'perm_update'
    | 'perm_delete'
  )[];
  end?: number | null;
  order?: 'DESC' | 'ASC' | 'desc' | 'asc';
  sort?:
    | 'id'
    | 'active'
    | 'name'
    | 'model_id'
    | 'role_id'
    | 'perm_create'
    | 'perm_read'
    | 'perm_update'
    | 'perm_delete';
  start?: number | null;
  limit?: number;
  filter?: (
    | ['id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['active', '=' | '!=', boolean]
    | [
        'name',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | ['model_id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['role_id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['perm_create', '=' | '!=', boolean]
    | ['perm_read', '=' | '!=', boolean]
    | ['perm_update', '=' | '!=', boolean]
    | ['perm_delete', '=' | '!=', boolean]
  )[];
  raw?: boolean;
};
export type SchemaCreateOutput = {
  id: number;
};
export type AccessListCreate = {
  active?: boolean;
  name: string;
  model_id: number | 'VirtualId';
  role_id: number | 'VirtualId';
  perm_create: boolean;
  perm_read: boolean;
  perm_update: boolean;
  perm_delete: boolean;
};
export type SchemaModelNestedPartial = {
  id?: number | null;
  name?: string | null;
};
export type SchemaRoleNestedPartial = {
  id?: number | null;
  name?: string | null;
  model_id?: SchemaRelationNested | null;
  user_ids?: SchemaRelationNested[] | null;
  acl_ids?: SchemaRelationNested[] | null;
  rule_ids?: SchemaRelationNested[] | null;
};
export type AccessList = {
  id: number;
  active?: boolean;
  name: string;
  model_id: SchemaModelNestedPartial;
  role_id: SchemaRoleNestedPartial;
  perm_create: boolean;
  perm_read: boolean;
  perm_update: boolean;
  perm_delete: boolean;
};
export type GetFormField = {
  name: string;
  type: string;
  relatedModel?: string | null;
  relatedField?: string | null;
  options?: any[] | null;
};
export type SchemaGetOutputAccessList = {
  data: AccessList;
  fields: {
    [key: string]: GetFormField;
  };
};
export type SchemaGetInput = {
  fields: (
    | 'id'
    | 'active'
    | 'name'
    | 'model_id'
    | 'role_id'
    | 'perm_create'
    | 'perm_read'
    | 'perm_update'
    | 'perm_delete'
  )[];
};
export type AccessListUpdate = {
  active?: boolean | null;
  name?: string | null;
  model_id?: number | 'VirtualId' | null;
  role_id?: number | 'VirtualId' | null;
  perm_create?: boolean | null;
  perm_read?: boolean | null;
  perm_update?: boolean | null;
  perm_delete?: boolean | null;
};
export type SchemaGetInput2 = {
  fields: (
    | 'id'
    | 'active'
    | 'name'
    | 'model_id'
    | 'role_id'
    | 'perm_create'
    | 'perm_read'
    | 'perm_update'
    | 'perm_delete'
  )[];
};
export const {
  useRouteAccessListSearchPostMutation,
  useRouteAccessListSearchMany2ManyGetQuery,
  useLazyRouteAccessListSearchMany2ManyGetQuery,
  useRouteAccessListPostMutation,
  useRouteAccessListDefaultValuesPostMutation,
  useRouteAccessListIdPutMutation,
  useRouteAccessListIdDeleteMutation,
  useRouteAccessListIdPostMutation,
  useRouteAccessListBulkDeleteMutation,
} = injectedRtkApi;
