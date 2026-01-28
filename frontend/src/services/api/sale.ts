import { crudApi as api } from './crudApi';
const injectedRtkApi = api.injectEndpoints({
  endpoints: build => ({
    routeSaleSearchPost: build.mutation<
      RouteSaleSearchPostApiResponse,
      RouteSaleSearchPostApiArg
    >({
      query: queryArg => ({
        url: `/sale/search`,
        method: 'POST',
        body: queryArg.saleSearchInput,
      }),
    }),
    routeSaleSearchMany2ManyGet: build.query<
      RouteSaleSearchMany2ManyGetApiResponse,
      RouteSaleSearchMany2ManyGetApiArg
    >({
      query: queryArg => ({
        url: `/sale/search_many2many`,
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
    routeSalePost: build.mutation<
      RouteSalePostApiResponse,
      RouteSalePostApiArg
    >({
      query: queryArg => ({
        url: `/sale`,
        method: 'POST',
        body: queryArg.saleCreate,
      }),
    }),
    routeSaleDefaultValuesPost: build.mutation<
      RouteSaleDefaultValuesPostApiResponse,
      RouteSaleDefaultValuesPostApiArg
    >({
      query: queryArg => ({
        url: `/sale/default_values`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput23,
      }),
    }),
    routeSaleIdPut: build.mutation<
      RouteSaleIdPutApiResponse,
      RouteSaleIdPutApiArg
    >({
      query: queryArg => ({
        url: `/sale/${queryArg.id}`,
        method: 'PUT',
        body: queryArg.saleUpdateInput,
      }),
    }),
    routeSaleIdDelete: build.mutation<
      RouteSaleIdDeleteApiResponse,
      RouteSaleIdDeleteApiArg
    >({
      query: queryArg => ({ url: `/sale/${queryArg.id}`, method: 'DELETE' }),
    }),
    routeSaleIdPost: build.mutation<
      RouteSaleIdPostApiResponse,
      RouteSaleIdPostApiArg
    >({
      query: queryArg => ({
        url: `/sale/${queryArg.id}`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput24,
      }),
    }),
    routeSaleBulkDelete: build.mutation<
      RouteSaleBulkDeleteApiResponse,
      RouteSaleBulkDeleteApiArg
    >({
      query: queryArg => ({
        url: `/sale/bulk`,
        method: 'DELETE',
        body: queryArg.ids,
      }),
    }),
    routeSaleLineSearchPost: build.mutation<
      RouteSaleLineSearchPostApiResponse,
      RouteSaleLineSearchPostApiArg
    >({
      query: queryArg => ({
        url: `/sale_line/search`,
        method: 'POST',
        body: queryArg.saleLineSearchInput,
      }),
    }),
    routeSaleLineSearchMany2ManyGet: build.query<
      RouteSaleLineSearchMany2ManyGetApiResponse,
      RouteSaleLineSearchMany2ManyGetApiArg
    >({
      query: queryArg => ({
        url: `/sale_line/search_many2many`,
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
    routeSaleLinePost: build.mutation<
      RouteSaleLinePostApiResponse,
      RouteSaleLinePostApiArg
    >({
      query: queryArg => ({
        url: `/sale_line`,
        method: 'POST',
        body: queryArg.saleLineCreate,
      }),
    }),
    routeSaleLineDefaultValuesPost: build.mutation<
      RouteSaleLineDefaultValuesPostApiResponse,
      RouteSaleLineDefaultValuesPostApiArg
    >({
      query: queryArg => ({
        url: `/sale_line/default_values`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput25,
      }),
    }),
    routeSaleLineIdPut: build.mutation<
      RouteSaleLineIdPutApiResponse,
      RouteSaleLineIdPutApiArg
    >({
      query: queryArg => ({
        url: `/sale_line/${queryArg.id}`,
        method: 'PUT',
        body: queryArg.saleLineUpdate,
      }),
    }),
    routeSaleLineIdDelete: build.mutation<
      RouteSaleLineIdDeleteApiResponse,
      RouteSaleLineIdDeleteApiArg
    >({
      query: queryArg => ({
        url: `/sale_line/${queryArg.id}`,
        method: 'DELETE',
      }),
    }),
    routeSaleLineIdPost: build.mutation<
      RouteSaleLineIdPostApiResponse,
      RouteSaleLineIdPostApiArg
    >({
      query: queryArg => ({
        url: `/sale_line/${queryArg.id}`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput26,
      }),
    }),
    routeSaleLineBulkDelete: build.mutation<
      RouteSaleLineBulkDeleteApiResponse,
      RouteSaleLineBulkDeleteApiArg
    >({
      query: queryArg => ({
        url: `/sale_line/bulk`,
        method: 'DELETE',
        body: queryArg.ids,
      }),
    }),
  }),
  overrideExisting: false,
});
export { injectedRtkApi as crudApi };
export type RouteSaleSearchPostApiResponse =
  /** status 200 успешно */ SchemaSearchOutputListSaleReadSearchOutput;
export type RouteSaleSearchPostApiArg = {
  saleSearchInput: SaleSearchInput;
};
export type RouteSaleSearchMany2ManyGetApiResponse =
  /** status 200 успешно */ any;
export type RouteSaleSearchMany2ManyGetApiArg = {
  id: number;
  name: null;
  fields: string[];
  order?: 'desc' | 'asc';
  start?: number | null;
  end?: number | null;
  sort?: string;
  limit?: number;
};
export type RouteSalePostApiResponse =
  /** status 200 успешно */ SchemaCreateOutput;
export type RouteSalePostApiArg = {
  saleCreate: SaleCreate;
};
export type RouteSaleDefaultValuesPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputSale;
export type RouteSaleDefaultValuesPostApiArg = {
  backendBaseSystemDotormDotormUtilsSchemaGetInput23: SchemaGetInput;
};
export type RouteSaleIdPutApiResponse = /** status 200 успешно */ SaleUpdate;
export type RouteSaleIdPutApiArg = {
  id: number;
  saleUpdateInput: SaleUpdate2;
};
export type RouteSaleIdDeleteApiResponse = /** status 200 успешно */ true;
export type RouteSaleIdDeleteApiArg = {
  id: number;
};
export type RouteSaleIdPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputSale;
export type RouteSaleIdPostApiArg = {
  id: number;
  backendBaseSystemDotormDotormUtilsSchemaGetInput24: SchemaGetInput2;
};
export type RouteSaleBulkDeleteApiResponse = /** status 200 успешно */ true;
export type RouteSaleBulkDeleteApiArg = {
  ids: number[];
};
export type RouteSaleLineSearchPostApiResponse =
  /** status 200 успешно */ SchemaSearchOutputListSaleLineReadSearchOutput;
export type RouteSaleLineSearchPostApiArg = {
  saleLineSearchInput: SaleLineSearchInput;
};
export type RouteSaleLineSearchMany2ManyGetApiResponse =
  /** status 200 успешно */ any;
export type RouteSaleLineSearchMany2ManyGetApiArg = {
  id: number;
  name: null;
  fields: string[];
  order?: 'desc' | 'asc';
  start?: number | null;
  end?: number | null;
  sort?: string;
  limit?: number;
};
export type RouteSaleLinePostApiResponse =
  /** status 200 успешно */ SchemaCreateOutput;
export type RouteSaleLinePostApiArg = {
  saleLineCreate: SaleLineCreate;
};
export type RouteSaleLineDefaultValuesPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputSaleLine;
export type RouteSaleLineDefaultValuesPostApiArg = {
  backendBaseSystemDotormDotormUtilsSchemaGetInput25: SchemaGetInput3;
};
export type RouteSaleLineIdPutApiResponse =
  /** status 200 успешно */ SaleLineUpdate;
export type RouteSaleLineIdPutApiArg = {
  id: number;
  saleLineUpdate: SaleLineUpdate;
};
export type RouteSaleLineIdDeleteApiResponse = /** status 200 успешно */ true;
export type RouteSaleLineIdDeleteApiArg = {
  id: number;
};
export type RouteSaleLineIdPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputSaleLine;
export type RouteSaleLineIdPostApiArg = {
  id: number;
  backendBaseSystemDotormDotormUtilsSchemaGetInput26: SchemaGetInput4;
};
export type RouteSaleLineBulkDeleteApiResponse = /** status 200 успешно */ true;
export type RouteSaleLineBulkDeleteApiArg = {
  ids: number[];
};
export type SchemaRelationNested = {
  id: number;
  name: string;
};
export type SaleReadSearchOutput = {
  id?: number | null;
  name?: string | null;
  active?: boolean | null;
  user_id?: SchemaRelationNested | null;
  parent_id?: SchemaRelationNested | null;
  company_id?: SchemaRelationNested | null;
  order_line_ids?: SchemaRelationNested[] | null;
  notes?: string | null;
  date_order?: string | null;
  origin?: string | null;
  website?: string | null;
  email?: string | null;
  phone?: string | null;
  mobile?: string | null;
};
export type GetListField = {
  name: string;
  type: string;
  relation?: string | null;
};
export type SchemaSearchOutputListSaleReadSearchOutput = {
  data: SaleReadSearchOutput[];
  total?: number | null;
  fields: GetListField[];
};
export type SaleSearchInput = {
  fields: (
    | 'id'
    | 'name'
    | 'active'
    | 'user_id'
    | 'parent_id'
    | 'company_id'
    | 'order_line_ids'
    | 'notes'
    | 'date_order'
    | 'origin'
    | 'website'
    | 'email'
    | 'phone'
    | 'mobile'
  )[];
  end?: number | null;
  order?: 'DESC' | 'ASC' | 'desc' | 'asc';
  sort?:
    | 'id'
    | 'name'
    | 'active'
    | 'user_id'
    | 'parent_id'
    | 'company_id'
    | 'order_line_ids'
    | 'notes'
    | 'date_order'
    | 'origin'
    | 'website'
    | 'email'
    | 'phone'
    | 'mobile';
  start?: number | null;
  limit?: number;
  filter?: (
    | ['id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | [
        'name',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | ['active', '=' | '!=', boolean]
    | ['user_id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['parent_id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['company_id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['order_line_ids', 'in' | 'not in', number[]]
    | [
        'notes',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | ['date_order', '=' | '>' | '<' | '!=' | '>=' | '<=', string]
    | [
        'origin',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | [
        'website',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | [
        'email',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | [
        'phone',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | [
        'mobile',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
  )[];
  raw?: boolean;
};
export type SchemaCreateOutput = {
  id: number;
};
export type SchemaSaleLineRelationNestedUpdate = {
  sale_id?: number | 'VirtualId' | null;
  sequence?: number | null;
  notes?: string | null;
  product_id?: number | 'VirtualId' | null;
  product_uom_qty?: number | null;
  product_uom_id?: number | 'VirtualId' | null;
  tax_id?: number | 'VirtualId' | null;
  price_unit?: number | null;
  discount?: number | null;
  price_subtotal?: number | null;
  price_tax?: number | null;
  price_total?: number | null;
};
export type SchemaRelationOne2ManyUpdateCreateSchemaSaleLineRelationNestedUpdate =
  {
    created?: SchemaSaleLineRelationNestedUpdate[];
    deleted?: number[];
  };
export type SaleCreate = {
  name: string;
  active?: boolean;
  user_id: number | 'VirtualId';
  parent_id: number | 'VirtualId';
  company_id: number | 'VirtualId';
  order_line_ids: SchemaRelationOne2ManyUpdateCreateSchemaSaleLineRelationNestedUpdate;
  notes: string;
  date_order?: string;
  origin: string;
  website: string;
  email: string;
  phone: string;
  mobile: string;
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
export type SchemaPartnerNestedPartial = {
  id?: number | null;
  name?: string | null;
  active?: boolean | null;
  parent_id?: SchemaRelationNested | null;
  child_ids?: SchemaRelationNested[] | null;
  user_id?: SchemaRelationNested | null;
  company_id?: SchemaRelationNested | null;
  tz?: string | null;
  lang?: string | null;
  vat?: string | null;
  notes?: string | null;
  website?: string | null;
  email?: string | null;
  phone?: string | null;
  mobile?: string | null;
};
export type SchemaCompanyNestedPartial = {
  id?: number | null;
  name?: string | null;
  active?: boolean | null;
  sequence?: number | null;
  parent_id?: SchemaRelationNested | null;
  child_ids?: SchemaRelationNested[] | null;
};
export type SchemaSaleLineNestedPartial = {
  id?: number | null;
  sale_id?: SchemaRelationNested | null;
  sequence?: number | null;
  notes?: string | null;
  product_id?: SchemaRelationNested | null;
  product_uom_qty?: number | null;
  product_uom_id?: SchemaRelationNested | null;
  tax_id?: SchemaRelationNested | null;
  price_unit?: number | null;
  discount?: number | null;
  price_subtotal?: number | null;
  price_tax?: number | null;
  price_total?: number | null;
};
export type SchemaSearchOutputListSchemaSaleLineNestedPartial = {
  data: SchemaSaleLineNestedPartial[];
  total?: number | null;
  fields: GetListField[];
};
export type Sale = {
  id: number;
  name: string;
  active?: boolean;
  user_id: SchemaUserNestedPartial;
  parent_id: SchemaPartnerNestedPartial;
  company_id: SchemaCompanyNestedPartial;
  order_line_ids: SchemaSearchOutputListSchemaSaleLineNestedPartial;
  notes: string;
  date_order?: string;
  origin: string;
  website: string;
  email: string;
  phone: string;
  mobile: string;
};
export type GetFormField = {
  name: string;
  type: string;
  relatedModel?: string | null;
  relatedField?: string | null;
  options?: any[] | null;
};
export type SchemaGetOutputSale = {
  data: Sale;
  fields: {
    [key: string]: GetFormField;
  };
};
export type SchemaGetFieldRelationInput = {
  order_line_ids: (
    | 'id'
    | 'sale_id'
    | 'sequence'
    | 'notes'
    | 'product_id'
    | 'product_uom_qty'
    | 'product_uom_id'
    | 'tax_id'
    | 'price_unit'
    | 'discount'
    | 'price_subtotal'
    | 'price_tax'
    | 'price_total'
  )[];
};
export type SchemaGetInput = {
  fields: (
    | (
        | 'id'
        | 'name'
        | 'active'
        | 'user_id'
        | 'parent_id'
        | 'company_id'
        | 'notes'
        | 'date_order'
        | 'origin'
        | 'website'
        | 'email'
        | 'phone'
        | 'mobile'
      )
    | SchemaGetFieldRelationInput
  )[];
};
export type SaleUpdate = {
  name?: string | null;
  active?: boolean | null;
  user_id?: number | 'VirtualId' | null;
  parent_id?: number | 'VirtualId' | null;
  company_id?: number | 'VirtualId' | null;
  order_line_ids?: SchemaRelationOne2ManyUpdateCreateSchemaSaleLineRelationNestedUpdate | null;
  notes?: string | null;
  date_order?: string | null;
  origin?: string | null;
  website?: string | null;
  email?: string | null;
  phone?: string | null;
  mobile?: string | null;
};
export type SaleUpdate2 = {
  name?: string | null;
  active?: boolean | null;
  user_id?: number | 'VirtualId' | null;
  parent_id?: number | 'VirtualId' | null;
  company_id?: number | 'VirtualId' | null;
  order_line_ids?: SchemaRelationOne2ManyUpdateCreateSchemaSaleLineRelationNestedUpdate | null;
  notes?: string | null;
  date_order?: string | null;
  origin?: string | null;
  website?: string | null;
  email?: string | null;
  phone?: string | null;
  mobile?: string | null;
};
export type SchemaGetFieldRelationInput2 = {
  order_line_ids: (
    | 'id'
    | 'sale_id'
    | 'sequence'
    | 'notes'
    | 'product_id'
    | 'product_uom_qty'
    | 'product_uom_id'
    | 'tax_id'
    | 'price_unit'
    | 'discount'
    | 'price_subtotal'
    | 'price_tax'
    | 'price_total'
  )[];
};
export type SchemaGetInput2 = {
  fields: (
    | (
        | 'id'
        | 'name'
        | 'active'
        | 'user_id'
        | 'parent_id'
        | 'company_id'
        | 'notes'
        | 'date_order'
        | 'origin'
        | 'website'
        | 'email'
        | 'phone'
        | 'mobile'
      )
    | SchemaGetFieldRelationInput2
  )[];
};
export type SaleLineReadSearchOutput = {
  id?: number | null;
  sale_id?: SchemaRelationNested | null;
  sequence?: number | null;
  notes?: string | null;
  product_id?: SchemaRelationNested | null;
  product_uom_qty?: number | null;
  product_uom_id?: SchemaRelationNested | null;
  tax_id?: SchemaRelationNested | null;
  price_unit?: number | null;
  discount?: number | null;
  price_subtotal?: number | null;
  price_tax?: number | null;
  price_total?: number | null;
};
export type SchemaSearchOutputListSaleLineReadSearchOutput = {
  data: SaleLineReadSearchOutput[];
  total?: number | null;
  fields: GetListField[];
};
export type SaleLineSearchInput = {
  fields: (
    | 'id'
    | 'sale_id'
    | 'sequence'
    | 'notes'
    | 'product_id'
    | 'product_uom_qty'
    | 'product_uom_id'
    | 'tax_id'
    | 'price_unit'
    | 'discount'
    | 'price_subtotal'
    | 'price_tax'
    | 'price_total'
  )[];
  end?: number | null;
  order?: 'DESC' | 'ASC' | 'desc' | 'asc';
  sort?:
    | 'id'
    | 'sale_id'
    | 'sequence'
    | 'notes'
    | 'product_id'
    | 'product_uom_qty'
    | 'product_uom_id'
    | 'tax_id'
    | 'price_unit'
    | 'discount'
    | 'price_subtotal'
    | 'price_tax'
    | 'price_total';
  start?: number | null;
  limit?: number;
  filter?: (
    | ['id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['sale_id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['sequence', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | [
        'notes',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | ['product_id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['product_uom_qty', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['product_uom_id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['tax_id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['price_unit', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['discount', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['price_subtotal', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['price_tax', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['price_total', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
  )[];
  raw?: boolean;
};
export type SaleLineCreate = {
  sale_id: number | 'VirtualId';
  sequence?: number;
  notes: string;
  product_id: number | 'VirtualId';
  product_uom_qty?: number;
  product_uom_id: number | 'VirtualId';
  tax_id: number | 'VirtualId';
  price_unit: number;
  discount: number;
  price_subtotal: number;
  price_tax: number;
  price_total: number;
};
export type SchemaSaleNestedPartial = {
  id?: number | null;
  name?: string | null;
  active?: boolean | null;
  user_id?: SchemaRelationNested | null;
  parent_id?: SchemaRelationNested | null;
  company_id?: SchemaRelationNested | null;
  order_line_ids?: SchemaRelationNested[] | null;
  notes?: string | null;
  date_order?: string | null;
  origin?: string | null;
  website?: string | null;
  email?: string | null;
  phone?: string | null;
  mobile?: string | null;
};
export type SchemaProductNestedPartial = {
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
export type SchemaUomNestedPartial = {
  id?: number | null;
  name?: string | null;
};
export type SchemaTaxNestedPartial = {
  id?: number | null;
  name?: string | null;
};
export type SaleLine = {
  id: number;
  sale_id: SchemaSaleNestedPartial;
  sequence?: number;
  notes: string;
  product_id: SchemaProductNestedPartial;
  product_uom_qty?: number;
  product_uom_id: SchemaUomNestedPartial;
  tax_id: SchemaTaxNestedPartial;
  price_unit: number;
  discount: number;
  price_subtotal: number;
  price_tax: number;
  price_total: number;
};
export type SchemaGetOutputSaleLine = {
  data: SaleLine;
  fields: {
    [key: string]: GetFormField;
  };
};
export type SchemaGetInput3 = {
  fields: (
    | 'id'
    | 'sale_id'
    | 'sequence'
    | 'notes'
    | 'product_id'
    | 'product_uom_qty'
    | 'product_uom_id'
    | 'tax_id'
    | 'price_unit'
    | 'discount'
    | 'price_subtotal'
    | 'price_tax'
    | 'price_total'
  )[];
};
export type SaleLineUpdate = {
  sale_id?: number | 'VirtualId' | null;
  sequence?: number | null;
  notes?: string | null;
  product_id?: number | 'VirtualId' | null;
  product_uom_qty?: number | null;
  product_uom_id?: number | 'VirtualId' | null;
  tax_id?: number | 'VirtualId' | null;
  price_unit?: number | null;
  discount?: number | null;
  price_subtotal?: number | null;
  price_tax?: number | null;
  price_total?: number | null;
};
export type SchemaGetInput4 = {
  fields: (
    | 'id'
    | 'sale_id'
    | 'sequence'
    | 'notes'
    | 'product_id'
    | 'product_uom_qty'
    | 'product_uom_id'
    | 'tax_id'
    | 'price_unit'
    | 'discount'
    | 'price_subtotal'
    | 'price_tax'
    | 'price_total'
  )[];
};
export const {
  useRouteSaleSearchPostMutation,
  useRouteSaleSearchMany2ManyGetQuery,
  useLazyRouteSaleSearchMany2ManyGetQuery,
  useRouteSalePostMutation,
  useRouteSaleDefaultValuesPostMutation,
  useRouteSaleIdPutMutation,
  useRouteSaleIdDeleteMutation,
  useRouteSaleIdPostMutation,
  useRouteSaleBulkDeleteMutation,
  useRouteSaleLineSearchPostMutation,
  useRouteSaleLineSearchMany2ManyGetQuery,
  useLazyRouteSaleLineSearchMany2ManyGetQuery,
  useRouteSaleLinePostMutation,
  useRouteSaleLineDefaultValuesPostMutation,
  useRouteSaleLineIdPutMutation,
  useRouteSaleLineIdDeleteMutation,
  useRouteSaleLineIdPostMutation,
  useRouteSaleLineBulkDeleteMutation,
} = injectedRtkApi;
