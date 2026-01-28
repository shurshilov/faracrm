import { crudApi as api } from './crudApi';
const injectedRtkApi = api.injectEndpoints({
  endpoints: build => ({
    routeCategorySearchPost: build.mutation<
      RouteCategorySearchPostApiResponse,
      RouteCategorySearchPostApiArg
    >({
      query: queryArg => ({
        url: `/category/search`,
        method: 'POST',
        body: queryArg.categorySearchInput,
      }),
    }),
    routeCategorySearchMany2ManyGet: build.query<
      RouteCategorySearchMany2ManyGetApiResponse,
      RouteCategorySearchMany2ManyGetApiArg
    >({
      query: queryArg => ({
        url: `/category/search_many2many`,
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
    routeCategoryPost: build.mutation<
      RouteCategoryPostApiResponse,
      RouteCategoryPostApiArg
    >({
      query: queryArg => ({
        url: `/category`,
        method: 'POST',
        body: queryArg.categoryCreate,
      }),
    }),
    routeCategoryDefaultValuesPost: build.mutation<
      RouteCategoryDefaultValuesPostApiResponse,
      RouteCategoryDefaultValuesPostApiArg
    >({
      query: queryArg => ({
        url: `/category/default_values`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput7,
      }),
    }),
    routeCategoryIdPut: build.mutation<
      RouteCategoryIdPutApiResponse,
      RouteCategoryIdPutApiArg
    >({
      query: queryArg => ({
        url: `/category/${queryArg.id}`,
        method: 'PUT',
        body: queryArg.categoryUpdate,
      }),
    }),
    routeCategoryIdDelete: build.mutation<
      RouteCategoryIdDeleteApiResponse,
      RouteCategoryIdDeleteApiArg
    >({
      query: queryArg => ({
        url: `/category/${queryArg.id}`,
        method: 'DELETE',
      }),
    }),
    routeCategoryIdPost: build.mutation<
      RouteCategoryIdPostApiResponse,
      RouteCategoryIdPostApiArg
    >({
      query: queryArg => ({
        url: `/category/${queryArg.id}`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput8,
      }),
    }),
    routeCategoryBulkDelete: build.mutation<
      RouteCategoryBulkDeleteApiResponse,
      RouteCategoryBulkDeleteApiArg
    >({
      query: queryArg => ({
        url: `/category/bulk`,
        method: 'DELETE',
        body: queryArg.ids,
      }),
    }),
  }),
  overrideExisting: false,
});
export { injectedRtkApi as crudApi };
export type RouteCategorySearchPostApiResponse =
  /** status 200 успешно */ SchemaSearchOutputListCategoryReadSearchOutput;
export type RouteCategorySearchPostApiArg = {
  categorySearchInput: CategorySearchInput;
};
export type RouteCategorySearchMany2ManyGetApiResponse =
  /** status 200 успешно */ any;
export type RouteCategorySearchMany2ManyGetApiArg = {
  id: number;
  name: null;
  fields: string[];
  order?: 'desc' | 'asc';
  start?: number | null;
  end?: number | null;
  sort?: string;
  limit?: number;
};
export type RouteCategoryPostApiResponse =
  /** status 200 успешно */ SchemaCreateOutput;
export type RouteCategoryPostApiArg = {
  categoryCreate: CategoryCreate;
};
export type RouteCategoryDefaultValuesPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputCategory;
export type RouteCategoryDefaultValuesPostApiArg = {
  backendBaseSystemDotormDotormUtilsSchemaGetInput7: SchemaGetInput;
};
export type RouteCategoryIdPutApiResponse =
  /** status 200 успешно */ CategoryUpdate;
export type RouteCategoryIdPutApiArg = {
  id: number;
  categoryUpdate: CategoryUpdate;
};
export type RouteCategoryIdDeleteApiResponse = /** status 200 успешно */ true;
export type RouteCategoryIdDeleteApiArg = {
  id: number;
};
export type RouteCategoryIdPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputCategory;
export type RouteCategoryIdPostApiArg = {
  id: number;
  backendBaseSystemDotormDotormUtilsSchemaGetInput8: SchemaGetInput2;
};
export type RouteCategoryBulkDeleteApiResponse = /** status 200 успешно */ true;
export type RouteCategoryBulkDeleteApiArg = {
  ids: number[];
};
export type CategoryReadSearchOutput = {
  id?: number | null;
  name?: string | null;
};
export type GetListField = {
  name: string;
  type: string;
  relation?: string | null;
};
export type SchemaSearchOutputListCategoryReadSearchOutput = {
  data: CategoryReadSearchOutput[];
  total?: number | null;
  fields: GetListField[];
};
export type CategorySearchInput = {
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
export type CategoryCreate = {
  name: string;
};
export type Category = {
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
export type SchemaGetOutputCategory = {
  data: Category;
  fields: {
    [key: string]: GetFormField;
  };
};
export type SchemaGetInput = {
  fields: ('id' | 'name')[];
};
export type CategoryUpdate = {
  name?: string | null;
};
export type SchemaGetInput2 = {
  fields: ('id' | 'name')[];
};
export const {
  useRouteCategorySearchPostMutation,
  useRouteCategorySearchMany2ManyGetQuery,
  useLazyRouteCategorySearchMany2ManyGetQuery,
  useRouteCategoryPostMutation,
  useRouteCategoryDefaultValuesPostMutation,
  useRouteCategoryIdPutMutation,
  useRouteCategoryIdDeleteMutation,
  useRouteCategoryIdPostMutation,
  useRouteCategoryBulkDeleteMutation,
} = injectedRtkApi;
