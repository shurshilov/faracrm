import { crudApi as api } from './crudApi';
const injectedRtkApi = api.injectEndpoints({
  endpoints: build => ({
    routeUomSearchPost: build.mutation<
      RouteUomSearchPostApiResponse,
      RouteUomSearchPostApiArg
    >({
      query: queryArg => ({
        url: `/uom/search`,
        method: 'POST',
        body: queryArg.uomSearchInput,
      }),
    }),
    routeUomSearchMany2ManyGet: build.query<
      RouteUomSearchMany2ManyGetApiResponse,
      RouteUomSearchMany2ManyGetApiArg
    >({
      query: queryArg => ({
        url: `/uom/search_many2many`,
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
    routeUomPost: build.mutation<RouteUomPostApiResponse, RouteUomPostApiArg>({
      query: queryArg => ({
        url: `/uom`,
        method: 'POST',
        body: queryArg.uomCreate,
      }),
    }),
    routeUomDefaultValuesPost: build.mutation<
      RouteUomDefaultValuesPostApiResponse,
      RouteUomDefaultValuesPostApiArg
    >({
      query: queryArg => ({
        url: `/uom/default_values`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput33,
      }),
    }),
    routeUomIdPut: build.mutation<
      RouteUomIdPutApiResponse,
      RouteUomIdPutApiArg
    >({
      query: queryArg => ({
        url: `/uom/${queryArg.id}`,
        method: 'PUT',
        body: queryArg.uomUpdate,
      }),
    }),
    routeUomIdDelete: build.mutation<
      RouteUomIdDeleteApiResponse,
      RouteUomIdDeleteApiArg
    >({
      query: queryArg => ({ url: `/uom/${queryArg.id}`, method: 'DELETE' }),
    }),
    routeUomIdPost: build.mutation<
      RouteUomIdPostApiResponse,
      RouteUomIdPostApiArg
    >({
      query: queryArg => ({
        url: `/uom/${queryArg.id}`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput34,
      }),
    }),
    routeUomBulkDelete: build.mutation<
      RouteUomBulkDeleteApiResponse,
      RouteUomBulkDeleteApiArg
    >({
      query: queryArg => ({
        url: `/uom/bulk`,
        method: 'DELETE',
        body: queryArg.ids,
      }),
    }),
  }),
  overrideExisting: false,
});
export { injectedRtkApi as crudApi };
export type RouteUomSearchPostApiResponse =
  /** status 200 успешно */ SchemaSearchOutputListUomReadSearchOutput;
export type RouteUomSearchPostApiArg = {
  uomSearchInput: UomSearchInput;
};
export type RouteUomSearchMany2ManyGetApiResponse =
  /** status 200 успешно */ any;
export type RouteUomSearchMany2ManyGetApiArg = {
  id: number;
  name: null;
  fields: string[];
  order?: 'desc' | 'asc';
  start?: number | null;
  end?: number | null;
  sort?: string;
  limit?: number;
};
export type RouteUomPostApiResponse =
  /** status 200 успешно */ SchemaCreateOutput;
export type RouteUomPostApiArg = {
  uomCreate: UomCreate;
};
export type RouteUomDefaultValuesPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputUom;
export type RouteUomDefaultValuesPostApiArg = {
  backendBaseSystemDotormDotormUtilsSchemaGetInput33: SchemaGetInput;
};
export type RouteUomIdPutApiResponse = /** status 200 успешно */ UomUpdate;
export type RouteUomIdPutApiArg = {
  id: number;
  uomUpdate: UomUpdate;
};
export type RouteUomIdDeleteApiResponse = /** status 200 успешно */ true;
export type RouteUomIdDeleteApiArg = {
  id: number;
};
export type RouteUomIdPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputUom;
export type RouteUomIdPostApiArg = {
  id: number;
  backendBaseSystemDotormDotormUtilsSchemaGetInput34: SchemaGetInput2;
};
export type RouteUomBulkDeleteApiResponse = /** status 200 успешно */ true;
export type RouteUomBulkDeleteApiArg = {
  ids: number[];
};
export type UomReadSearchOutput = {
  id?: number | null;
  name?: string | null;
};
export type GetListField = {
  name: string;
  type: string;
  relation?: string | null;
};
export type SchemaSearchOutputListUomReadSearchOutput = {
  data: UomReadSearchOutput[];
  total?: number | null;
  fields: GetListField[];
};
export type UomSearchInput = {
  fields: ('id' | 'name')[];
  end?: number | null;
  order?: 'DESC' | 'ASC' | 'desc' | 'asc';
  sort?: 'id' | 'name';
  start?: number | null;
  limit?: number;
  filter?: (
    | ['id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | [
        'name',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
  )[];
  raw?: boolean;
};
export type SchemaCreateOutput = {
  id: number;
};
export type UomCreate = {
  name: string;
};
export type Uom = {
  id: number;
  name: string;
};
export type GetFormField = {
  name: string;
  type: string;
  relatedModel?: string | null;
  relatedField?: string | null;
  options?: any[] | null;
};
export type SchemaGetOutputUom = {
  data: Uom;
  fields: {
    [key: string]: GetFormField;
  };
};
export type SchemaGetInput = {
  fields: ('id' | 'name')[];
};
export type UomUpdate = {
  name?: string | null;
};
export type SchemaGetInput2 = {
  fields: ('id' | 'name')[];
};
export const {
  useRouteUomSearchPostMutation,
  useRouteUomSearchMany2ManyGetQuery,
  useLazyRouteUomSearchMany2ManyGetQuery,
  useRouteUomPostMutation,
  useRouteUomDefaultValuesPostMutation,
  useRouteUomIdPutMutation,
  useRouteUomIdDeleteMutation,
  useRouteUomIdPostMutation,
  useRouteUomBulkDeleteMutation,
} = injectedRtkApi;
