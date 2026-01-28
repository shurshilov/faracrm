import { crudApi as api } from './crudApi';
const injectedRtkApi = api.injectEndpoints({
  endpoints: build => ({
    routeModelsSearchPost: build.mutation<
      RouteModelsSearchPostApiResponse,
      RouteModelsSearchPostApiArg
    >({
      query: queryArg => ({
        url: `/models/search`,
        method: 'POST',
        body: queryArg.modelSearchInput,
      }),
    }),
    routeModelsSearchMany2ManyGet: build.query<
      RouteModelsSearchMany2ManyGetApiResponse,
      RouteModelsSearchMany2ManyGetApiArg
    >({
      query: queryArg => ({
        url: `/models/search_many2many`,
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
    routeModelsPost: build.mutation<
      RouteModelsPostApiResponse,
      RouteModelsPostApiArg
    >({
      query: queryArg => ({
        url: `/models`,
        method: 'POST',
        body: queryArg.modelCreate,
      }),
    }),
    routeModelsDefaultValuesPost: build.mutation<
      RouteModelsDefaultValuesPostApiResponse,
      RouteModelsDefaultValuesPostApiArg
    >({
      query: queryArg => ({
        url: `/models/default_values`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput13,
      }),
    }),
    routeModelsIdPut: build.mutation<
      RouteModelsIdPutApiResponse,
      RouteModelsIdPutApiArg
    >({
      query: queryArg => ({
        url: `/models/${queryArg.id}`,
        method: 'PUT',
        body: queryArg.modelUpdate,
      }),
    }),
    routeModelsIdDelete: build.mutation<
      RouteModelsIdDeleteApiResponse,
      RouteModelsIdDeleteApiArg
    >({
      query: queryArg => ({ url: `/models/${queryArg.id}`, method: 'DELETE' }),
    }),
    routeModelsIdPost: build.mutation<
      RouteModelsIdPostApiResponse,
      RouteModelsIdPostApiArg
    >({
      query: queryArg => ({
        url: `/models/${queryArg.id}`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput14,
      }),
    }),
    routeModelsBulkDelete: build.mutation<
      RouteModelsBulkDeleteApiResponse,
      RouteModelsBulkDeleteApiArg
    >({
      query: queryArg => ({
        url: `/models/bulk`,
        method: 'DELETE',
        body: queryArg.ids,
      }),
    }),
  }),
  overrideExisting: false,
});
export { injectedRtkApi as crudApi };
export type RouteModelsSearchPostApiResponse =
  /** status 200 успешно */ SchemaSearchOutputListModelReadSearchOutput;
export type RouteModelsSearchPostApiArg = {
  modelSearchInput: ModelSearchInput;
};
export type RouteModelsSearchMany2ManyGetApiResponse =
  /** status 200 успешно */ any;
export type RouteModelsSearchMany2ManyGetApiArg = {
  id: number;
  name: null;
  fields: string[];
  order?: 'desc' | 'asc';
  start?: number | null;
  end?: number | null;
  sort?: string;
  limit?: number;
};
export type RouteModelsPostApiResponse =
  /** status 200 успешно */ SchemaCreateOutput;
export type RouteModelsPostApiArg = {
  modelCreate: ModelCreate;
};
export type RouteModelsDefaultValuesPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputModel;
export type RouteModelsDefaultValuesPostApiArg = {
  backendBaseSystemDotormDotormUtilsSchemaGetInput13: SchemaGetInput;
};
export type RouteModelsIdPutApiResponse = /** status 200 успешно */ ModelUpdate;
export type RouteModelsIdPutApiArg = {
  id: number;
  modelUpdate: ModelUpdate;
};
export type RouteModelsIdDeleteApiResponse = /** status 200 успешно */ true;
export type RouteModelsIdDeleteApiArg = {
  id: number;
};
export type RouteModelsIdPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputModel;
export type RouteModelsIdPostApiArg = {
  id: number;
  backendBaseSystemDotormDotormUtilsSchemaGetInput14: SchemaGetInput2;
};
export type RouteModelsBulkDeleteApiResponse = /** status 200 успешно */ true;
export type RouteModelsBulkDeleteApiArg = {
  ids: number[];
};
export type ModelReadSearchOutput = {
  id?: number | null;
  name?: string | null;
};
export type GetListField = {
  name: string;
  type: string;
  relation?: string | null;
};
export type SchemaSearchOutputListModelReadSearchOutput = {
  data: ModelReadSearchOutput[];
  total?: number | null;
  fields: GetListField[];
};
export type ModelSearchInput = {
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
export type ModelCreate = {
  name: string;
};
export type Model = {
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
export type SchemaGetOutputModel = {
  data: Model;
  fields: {
    [key: string]: GetFormField;
  };
};
export type SchemaGetInput = {
  fields: ('id' | 'name')[];
};
export type ModelUpdate = {
  name?: string | null;
};
export type SchemaGetInput2 = {
  fields: ('id' | 'name')[];
};
export const {
  useRouteModelsSearchPostMutation,
  useRouteModelsSearchMany2ManyGetQuery,
  useLazyRouteModelsSearchMany2ManyGetQuery,
  useRouteModelsPostMutation,
  useRouteModelsDefaultValuesPostMutation,
  useRouteModelsIdPutMutation,
  useRouteModelsIdDeleteMutation,
  useRouteModelsIdPostMutation,
  useRouteModelsBulkDeleteMutation,
} = injectedRtkApi;
