import { crudApi as api } from './crudApi';
const injectedRtkApi = api.injectEndpoints({
  endpoints: build => ({
    routeTaxSearchPost: build.mutation<
      RouteTaxSearchPostApiResponse,
      RouteTaxSearchPostApiArg
    >({
      query: queryArg => ({
        url: `/tax/search`,
        method: 'POST',
        body: queryArg.taxSearchInput,
      }),
    }),
    routeTaxSearchMany2ManyGet: build.query<
      RouteTaxSearchMany2ManyGetApiResponse,
      RouteTaxSearchMany2ManyGetApiArg
    >({
      query: queryArg => ({
        url: `/tax/search_many2many`,
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
    routeTaxPost: build.mutation<RouteTaxPostApiResponse, RouteTaxPostApiArg>({
      query: queryArg => ({
        url: `/tax`,
        method: 'POST',
        body: queryArg.taxCreate,
      }),
    }),
    routeTaxDefaultValuesPost: build.mutation<
      RouteTaxDefaultValuesPostApiResponse,
      RouteTaxDefaultValuesPostApiArg
    >({
      query: queryArg => ({
        url: `/tax/default_values`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput29,
      }),
    }),
    routeTaxIdPut: build.mutation<
      RouteTaxIdPutApiResponse,
      RouteTaxIdPutApiArg
    >({
      query: queryArg => ({
        url: `/tax/${queryArg.id}`,
        method: 'PUT',
        body: queryArg.taxUpdate,
      }),
    }),
    routeTaxIdDelete: build.mutation<
      RouteTaxIdDeleteApiResponse,
      RouteTaxIdDeleteApiArg
    >({
      query: queryArg => ({ url: `/tax/${queryArg.id}`, method: 'DELETE' }),
    }),
    routeTaxIdPost: build.mutation<
      RouteTaxIdPostApiResponse,
      RouteTaxIdPostApiArg
    >({
      query: queryArg => ({
        url: `/tax/${queryArg.id}`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput30,
      }),
    }),
    routeTaxBulkDelete: build.mutation<
      RouteTaxBulkDeleteApiResponse,
      RouteTaxBulkDeleteApiArg
    >({
      query: queryArg => ({
        url: `/tax/bulk`,
        method: 'DELETE',
        body: queryArg.ids,
      }),
    }),
  }),
  overrideExisting: false,
});
export { injectedRtkApi as crudApi };
export type RouteTaxSearchPostApiResponse =
  /** status 200 успешно */ SchemaSearchOutputListTaxReadSearchOutput;
export type RouteTaxSearchPostApiArg = {
  taxSearchInput: TaxSearchInput;
};
export type RouteTaxSearchMany2ManyGetApiResponse =
  /** status 200 успешно */ any;
export type RouteTaxSearchMany2ManyGetApiArg = {
  id: number;
  name: null;
  fields: string[];
  order?: 'desc' | 'asc';
  start?: number | null;
  end?: number | null;
  sort?: string;
  limit?: number;
};
export type RouteTaxPostApiResponse =
  /** status 200 успешно */ SchemaCreateOutput;
export type RouteTaxPostApiArg = {
  taxCreate: TaxCreate;
};
export type RouteTaxDefaultValuesPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputTax;
export type RouteTaxDefaultValuesPostApiArg = {
  backendBaseSystemDotormDotormUtilsSchemaGetInput29: SchemaGetInput;
};
export type RouteTaxIdPutApiResponse = /** status 200 успешно */ TaxUpdate;
export type RouteTaxIdPutApiArg = {
  id: number;
  taxUpdate: TaxUpdate;
};
export type RouteTaxIdDeleteApiResponse = /** status 200 успешно */ true;
export type RouteTaxIdDeleteApiArg = {
  id: number;
};
export type RouteTaxIdPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputTax;
export type RouteTaxIdPostApiArg = {
  id: number;
  backendBaseSystemDotormDotormUtilsSchemaGetInput30: SchemaGetInput2;
};
export type RouteTaxBulkDeleteApiResponse = /** status 200 успешно */ true;
export type RouteTaxBulkDeleteApiArg = {
  ids: number[];
};
export type TaxReadSearchOutput = {
  id?: number | null;
  name?: string | null;
};
export type GetListField = {
  name: string;
  type: string;
  relation?: string | null;
};
export type SchemaSearchOutputListTaxReadSearchOutput = {
  data: TaxReadSearchOutput[];
  total?: number | null;
  fields: GetListField[];
};
export type TaxSearchInput = {
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
export type TaxCreate = {
  name: string;
};
export type Tax = {
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
export type SchemaGetOutputTax = {
  data: Tax;
  fields: {
    [key: string]: GetFormField;
  };
};
export type SchemaGetInput = {
  fields: ('id' | 'name')[];
};
export type TaxUpdate = {
  name?: string | null;
};
export type SchemaGetInput2 = {
  fields: ('id' | 'name')[];
};
export const {
  useRouteTaxSearchPostMutation,
  useRouteTaxSearchMany2ManyGetQuery,
  useLazyRouteTaxSearchMany2ManyGetQuery,
  useRouteTaxPostMutation,
  useRouteTaxDefaultValuesPostMutation,
  useRouteTaxIdPutMutation,
  useRouteTaxIdDeleteMutation,
  useRouteTaxIdPostMutation,
  useRouteTaxBulkDeleteMutation,
} = injectedRtkApi;
