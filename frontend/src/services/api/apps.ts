import { crudApi as api } from './crudApi';

const injectedRtkApi = api.injectEndpoints({
  endpoints: build => ({
    routeAppsSearchPost: build.mutation<
      RouteAppsSearchPostApiResponse,
      RouteAppsSearchPostApiArg
    >({
      query: queryArg => ({
        url: `/apps/search`,
        method: 'POST',
        body: queryArg.appSearchInput,
      }),
    }),
    routeAppsSearchMany2ManyGet: build.query<
      RouteAppsSearchMany2ManyGetApiResponse,
      RouteAppsSearchMany2ManyGetApiArg
    >({
      query: queryArg => ({
        url: `/apps/search_many2many`,
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
    routeAppsPost: build.mutation<
      RouteAppsPostApiResponse,
      RouteAppsPostApiArg
    >({
      query: queryArg => ({
        url: `/apps`,
        method: 'POST',
        body: queryArg.appCreate,
      }),
    }),
    routeAppsDefaultValuesPost: build.mutation<
      RouteAppsDefaultValuesPostApiResponse,
      RouteAppsDefaultValuesPostApiArg
    >({
      query: queryArg => ({
        url: `/apps/default_values`,
        method: 'POST',
        body: queryArg.schemaGetInput,
      }),
    }),
    routeAppsIdPut: build.mutation<
      RouteAppsIdPutApiResponse,
      RouteAppsIdPutApiArg
    >({
      query: queryArg => ({
        url: `/apps/${queryArg.id}`,
        method: 'PUT',
        body: queryArg.appUpdate,
      }),
    }),
    routeAppsIdDelete: build.mutation<
      RouteAppsIdDeleteApiResponse,
      RouteAppsIdDeleteApiArg
    >({
      query: queryArg => ({ url: `/apps/${queryArg.id}`, method: 'DELETE' }),
    }),
    routeAppsIdPost: build.mutation<
      RouteAppsIdPostApiResponse,
      RouteAppsIdPostApiArg
    >({
      query: queryArg => ({
        url: `/apps/${queryArg.id}`,
        method: 'POST',
        body: queryArg.schemaGetInput,
      }),
    }),
    routeAppsBulkDelete: build.mutation<
      RouteAppsBulkDeleteApiResponse,
      RouteAppsBulkDeleteApiArg
    >({
      query: queryArg => ({
        url: `/apps/bulk`,
        method: 'DELETE',
        body: queryArg.ids,
      }),
    }),
  }),
  overrideExisting: false,
});

export { injectedRtkApi as crudApi };

// Response types
export type RouteAppsSearchPostApiResponse =
  SchemaSearchOutputListAppReadSearchOutput;
export type RouteAppsSearchPostApiArg = {
  appSearchInput: AppSearchInput;
};
export type RouteAppsSearchMany2ManyGetApiResponse = any;
export type RouteAppsSearchMany2ManyGetApiArg = {
  id: number;
  name: null;
  fields: string[];
  order?: 'desc' | 'asc';
  start?: number | null;
  end?: number | null;
  sort?: string;
  limit?: number;
};
export type RouteAppsPostApiResponse = SchemaCreateOutput;
export type RouteAppsPostApiArg = {
  appCreate: AppCreate;
};
export type RouteAppsDefaultValuesPostApiResponse = SchemaGetOutputApp;
export type RouteAppsDefaultValuesPostApiArg = {
  schemaGetInput: SchemaGetInput;
};
export type RouteAppsIdPutApiResponse = AppUpdate;
export type RouteAppsIdPutApiArg = {
  id: number;
  appUpdate: AppUpdate;
};
export type RouteAppsIdDeleteApiResponse = true;
export type RouteAppsIdDeleteApiArg = {
  id: number;
};
export type RouteAppsIdPostApiResponse = SchemaGetOutputApp;
export type RouteAppsIdPostApiArg = {
  id: number;
  schemaGetInput: SchemaGetInput;
};
export type RouteAppsBulkDeleteApiResponse = true;
export type RouteAppsBulkDeleteApiArg = {
  ids: number[];
};

// Schema types
export type SchemaApp = {
  id?: number | null;
  code?: string | null;
  name?: string | null;
  active?: boolean | null;
};

export type AppReadSearchOutput = {
  id?: number | null;
  code?: string | null;
  name?: string | null;
  active?: boolean | null;
};

export type GetListField = {
  name: string;
  type: string;
  relation?: string | null;
};

export type SchemaSearchOutputListAppReadSearchOutput = {
  data: AppReadSearchOutput[];
  total?: number | null;
  fields: GetListField[];
};

export type AppSearchInput = {
  fields: ('id' | 'code' | 'name' | 'active')[];
  end?: number | null;
  order?: 'DESC' | 'ASC' | 'desc' | 'asc';
  sort?: 'id' | 'code' | 'name' | 'active';
  start?: number | null;
  limit?: number;
  filter?: (
    | ['id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | [
        'code',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | [
        'name',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | ['active', '=', boolean]
  )[];
  raw?: boolean;
};

export type SchemaCreateOutput = {
  id: number;
};

export type AppCreate = {
  code: string;
  name: string;
  active?: boolean;
};

export type App = {
  id: number;
  code: string;
  name: string;
  active: boolean;
};

export type GetFormField = {
  name: string;
  type: string;
  relatedModel?: string | null;
  relatedField?: string | null;
  options?: any[] | null;
};

export type SchemaGetOutputApp = {
  data: App;
  fields: {
    [key: string]: GetFormField;
  };
};

export type SchemaGetInput = {
  fields: ('id' | 'code' | 'name' | 'active')[];
};

export type AppUpdate = {
  code?: string | null;
  name?: string | null;
  active?: boolean | null;
};

export const {
  useRouteAppsSearchPostMutation,
  useRouteAppsSearchMany2ManyGetQuery,
  useLazyRouteAppsSearchMany2ManyGetQuery,
  useRouteAppsPostMutation,
  useRouteAppsDefaultValuesPostMutation,
  useRouteAppsIdPutMutation,
  useRouteAppsIdDeleteMutation,
  useRouteAppsIdPostMutation,
  useRouteAppsBulkDeleteMutation,
} = injectedRtkApi;
