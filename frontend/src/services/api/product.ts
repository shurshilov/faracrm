import { crudApi as api } from './crudApi';
const injectedRtkApi = api.injectEndpoints({
  endpoints: build => ({
    routeProductSearchPost: build.mutation<
      RouteProductSearchPostApiResponse,
      RouteProductSearchPostApiArg
    >({
      query: queryArg => ({
        url: `/product/search`,
        method: 'POST',
        body: queryArg.productSearchInput,
      }),
    }),
    routeProductSearchMany2ManyGet: build.query<
      RouteProductSearchMany2ManyGetApiResponse,
      RouteProductSearchMany2ManyGetApiArg
    >({
      query: queryArg => ({
        url: `/product/search_many2many`,
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
    routeProductPost: build.mutation<
      RouteProductPostApiResponse,
      RouteProductPostApiArg
    >({
      query: queryArg => ({
        url: `/product`,
        method: 'POST',
        body: queryArg.productCreate,
      }),
    }),
    routeProductDefaultValuesPost: build.mutation<
      RouteProductDefaultValuesPostApiResponse,
      RouteProductDefaultValuesPostApiArg
    >({
      query: queryArg => ({
        url: `/product/default_values`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput17,
      }),
    }),
    routeProductIdPut: build.mutation<
      RouteProductIdPutApiResponse,
      RouteProductIdPutApiArg
    >({
      query: queryArg => ({
        url: `/product/${queryArg.id}`,
        method: 'PUT',
        body: queryArg.productUpdateInput,
      }),
    }),
    routeProductIdDelete: build.mutation<
      RouteProductIdDeleteApiResponse,
      RouteProductIdDeleteApiArg
    >({
      query: queryArg => ({ url: `/product/${queryArg.id}`, method: 'DELETE' }),
    }),
    routeProductIdPost: build.mutation<
      RouteProductIdPostApiResponse,
      RouteProductIdPostApiArg
    >({
      query: queryArg => ({
        url: `/product/${queryArg.id}`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput18,
      }),
    }),
    routeProductBulkDelete: build.mutation<
      RouteProductBulkDeleteApiResponse,
      RouteProductBulkDeleteApiArg
    >({
      query: queryArg => ({
        url: `/product/bulk`,
        method: 'DELETE',
        body: queryArg.ids,
      }),
    }),
  }),
  overrideExisting: false,
});
export { injectedRtkApi as crudApi };
export type RouteProductSearchPostApiResponse =
  /** status 200 успешно */ SchemaSearchOutputListProductReadSearchOutput;
export type RouteProductSearchPostApiArg = {
  productSearchInput: ProductSearchInput;
};
export type RouteProductSearchMany2ManyGetApiResponse =
  /** status 200 успешно */ any;
export type RouteProductSearchMany2ManyGetApiArg = {
  id: number;
  name: null;
  fields: string[];
  order?: 'desc' | 'asc';
  start?: number | null;
  end?: number | null;
  sort?: string;
  limit?: number;
};
export type RouteProductPostApiResponse =
  /** status 200 успешно */ SchemaCreateOutput;
export type RouteProductPostApiArg = {
  productCreate: ProductCreate;
};
export type RouteProductDefaultValuesPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputProduct;
export type RouteProductDefaultValuesPostApiArg = {
  backendBaseSystemDotormDotormUtilsSchemaGetInput17: SchemaGetInput;
};
export type RouteProductIdPutApiResponse =
  /** status 200 успешно */ ProductUpdate;
export type RouteProductIdPutApiArg = {
  id: number;
  productUpdateInput: ProductUpdate2;
};
export type RouteProductIdDeleteApiResponse = /** status 200 успешно */ true;
export type RouteProductIdDeleteApiArg = {
  id: number;
};
export type RouteProductIdPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputProduct;
export type RouteProductIdPostApiArg = {
  id: number;
  backendBaseSystemDotormDotormUtilsSchemaGetInput18: SchemaGetInput2;
};
export type RouteProductBulkDeleteApiResponse = /** status 200 успешно */ true;
export type RouteProductBulkDeleteApiArg = {
  ids: number[];
};
export type SchemaRelationNested = {
  id: number;
  name: string;
};
export type ProductReadSearchOutput = {
  id?: number | null;
  name?: string | null;
  sequence?: number | null;
  type?: string | null;
  uom_id?: SchemaRelationNested | null;
  company_id?: SchemaRelationNested | null;
  category_id?: SchemaRelationNested | null;
  default_code?: string | null;
  code?: string | null;
  barcode?: string | null;
  extra_price?: number | null;
  list_price?: number | null;
  standard_price?: number | null;
  volume?: number | null;
  weight?: number | null;
  image?: SchemaRelationNested | null;
};
export type GetListField = {
  name: string;
  type: string;
  relation?: string | null;
};
export type SchemaSearchOutputListProductReadSearchOutput = {
  data: ProductReadSearchOutput[];
  total?: number | null;
  fields: GetListField[];
};
export type ProductSearchInput = {
  fields: (
    | 'id'
    | 'name'
    | 'sequence'
    | 'description'
    | 'type'
    | 'uom_id'
    | 'company_id'
    | 'category_id'
    | 'default_code'
    | 'code'
    | 'barcode'
    | 'extra_price'
    | 'list_price'
    | 'standard_price'
    | 'volume'
    | 'weight'
    | 'image'
  )[];
  end?: number | null;
  order?: 'DESC' | 'ASC' | 'desc' | 'asc';
  sort?:
    | 'id'
    | 'name'
    | 'sequence'
    | 'description'
    | 'type'
    | 'uom_id'
    | 'company_id'
    | 'category_id'
    | 'default_code'
    | 'code'
    | 'barcode'
    | 'extra_price'
    | 'list_price'
    | 'standard_price'
    | 'volume'
    | 'weight'
    | 'image';
  start?: number | null;
  limit?: number;
  filter?: (
    | ['id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | [
        'name',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | ['sequence', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | [
        'type',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | ['uom_id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['company_id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['category_id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | [
        'default_code',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | [
        'code',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | [
        'barcode',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | ['extra_price', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['list_price', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['standard_price', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['volume', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['weight', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['image', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
  )[];
  raw?: boolean;
};
export type SchemaCreateOutput = {
  id: number;
};
export type SchemaAttachmentStorage = {
  id: number;
  name: string;
  type?: string;
};
export type SchemaAttachment = {
  id: number;
  name: string | null;
  res_model: string | null;
  res_field: string | null;
  res_id: number | null;
  public: boolean | null;
  folder: boolean | null;
  access_token: string | null;
  size: number | null;
  checksum: string | null;
  mimetype: string | null;
  storage_id: SchemaAttachmentStorage | null;
  storage_file_id: string | null;
  storage_parent_id: string | null;
  storage_parent_name: string | null;
  storage_file_url: string | null;
  content: Blob | null;
};
export type ProductCreate = {
  name: string;
  sequence?: number;
  type?: string;
  uom_id: number | 'VirtualId';
  company_id: number | 'VirtualId';
  category_id: number | 'VirtualId';
  default_code: string;
  code: string;
  barcode: string;
  extra_price: number;
  list_price?: number;
  standard_price: number;
  volume: number;
  weight: number;
  image: SchemaAttachment | null;
};
export type SchemaUomNestedPartial = {
  id?: number | null;
  name?: string | null;
};
export type SchemaCompanyNestedPartial = {
  id?: number | null;
  name?: string | null;
  active?: boolean | null;
  sequence?: number | null;
  parent_id?: SchemaRelationNested | null;
  child_ids?: SchemaRelationNested[] | null;
};
export type SchemaCategoryNestedPartial = {
  id?: number | null;
  name?: string | null;
};
export type SchemaAttachmentNestedPartial = {
  id?: number | null;
  name?: string | null;
  res_model?: string | null;
  res_field?: string | null;
  res_id?: number | null;
  public?: boolean | null;
  folder?: boolean | null;
  access_token?: string | null;
  size?: number | null;
  checksum?: string | null;
  mimetype?: string | null;
  storage_id?: SchemaRelationNested | null;
  storage_file_id?: string | null;
  storage_parent_id?: string | null;
  storage_parent_name?: string | null;
  storage_file_url?: string | null;
  content?: Blob | null;
};
export type Product = {
  id: number;
  name: string;
  sequence?: number;
  type?: string;
  uom_id: SchemaUomNestedPartial;
  company_id: SchemaCompanyNestedPartial;
  category_id: SchemaCategoryNestedPartial;
  default_code: string;
  code: string;
  barcode: string;
  extra_price: number;
  list_price?: number;
  standard_price: number;
  volume: number;
  weight: number;
  image: SchemaAttachmentNestedPartial;
};
export type GetFormField = {
  name: string;
  type: string;
  relatedModel?: string | null;
  relatedField?: string | null;
  options?: any[] | null;
};
export type SchemaGetOutputProduct = {
  data: Product;
  fields: {
    [key: string]: GetFormField;
  };
};
export type SchemaGetInput = {
  fields: (
    | 'id'
    | 'name'
    | 'sequence'
    | 'description'
    | 'type'
    | 'uom_id'
    | 'company_id'
    | 'category_id'
    | 'default_code'
    | 'code'
    | 'barcode'
    | 'extra_price'
    | 'list_price'
    | 'standard_price'
    | 'volume'
    | 'weight'
    | 'image'
  )[];
};
export type ProductUpdate = {
  name?: string | null;
  sequence?: number | null;
  type?: string | null;
  uom_id?: number | 'VirtualId' | null;
  company_id?: number | 'VirtualId' | null;
  category_id?: number | 'VirtualId' | null;
  default_code?: string | null;
  code?: string | null;
  barcode?: string | null;
  extra_price?: number | null;
  list_price?: number | null;
  standard_price?: number | null;
  volume?: number | null;
  weight?: number | null;
  image?: SchemaAttachment | null;
};
export type ProductUpdate2 = {
  name?: string | null;
  sequence?: number | null;
  type?: string | null;
  uom_id?: number | 'VirtualId' | null;
  company_id?: number | 'VirtualId' | null;
  category_id?: number | 'VirtualId' | null;
  default_code?: string | null;
  code?: string | null;
  barcode?: string | null;
  extra_price?: number | null;
  list_price?: number | null;
  standard_price?: number | null;
  volume?: number | null;
  weight?: number | null;
  image?: SchemaAttachment | null;
};
export type SchemaGetInput2 = {
  fields: (
    | 'id'
    | 'name'
    | 'sequence'
    | 'description'
    | 'type'
    | 'uom_id'
    | 'company_id'
    | 'category_id'
    | 'default_code'
    | 'code'
    | 'barcode'
    | 'extra_price'
    | 'list_price'
    | 'standard_price'
    | 'volume'
    | 'weight'
    | 'image'
  )[];
};
export const {
  useRouteProductSearchPostMutation,
  useRouteProductSearchMany2ManyGetQuery,
  useLazyRouteProductSearchMany2ManyGetQuery,
  useRouteProductPostMutation,
  useRouteProductDefaultValuesPostMutation,
  useRouteProductIdPutMutation,
  useRouteProductIdDeleteMutation,
  useRouteProductIdPostMutation,
  useRouteProductBulkDeleteMutation,
} = injectedRtkApi;
