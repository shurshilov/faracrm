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
  fields: string[];
  order?: 'desc' | 'asc';
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
  fields: string[];
  order?: 'desc' | 'asc';
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
};
export type GetListField = {
  name: string;
  type: string;
};
export type SchemaSearchOutputListSaleReadSearchOutput = {
  data: SaleReadSearchOutput[];
  fields: GetListField[];
};
export type SaleSearchInput = {
  fields: (
    | 'id'
    | 'name'
    | 'active'
    | 'user_id'
    | 'partner_id'
    | 'company_id'
    | 'order_line_ids'
    | 'notes'
    | 'date_order'
    | 'origin'
  )[];
  order?: 'DESC' | 'ASC' | 'desc' | 'asc';
  sort?:
    | 'id'
    | 'name'
    | 'active'
    | 'user_id'
    | 'partner_id'
    | 'company_id'
    | 'order_line_ids'
    | 'notes'
    | 'date_order'
    | 'origin'
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
    | ['partner_id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
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
  partner_id: number | 'VirtualId';
  company_id: number | 'VirtualId';
  order_line_ids: SchemaRelationOne2ManyUpdateCreateSchemaSaleLineRelationNestedUpdate;
  notes: string;
  date_order?: string;
  origin: string;
};
export type SchemaUserNestedPartial = {
};
export type SchemaPartnerNestedPartial = {
};
export type SchemaCompanyNestedPartial = {
};
export type SchemaSaleLineNestedPartial = {
};
export type SchemaSearchOutputListSchemaSaleLineNestedPartial = {
  data: SchemaSaleLineNestedPartial[];
  fields: GetListField[];
};
export type Sale = {
  id: number;
  name: string;
  active?: boolean;
  user_id: SchemaUserNestedPartial;
  partner_id: SchemaPartnerNestedPartial;
  company_id: SchemaCompanyNestedPartial;
  order_line_ids: SchemaSearchOutputListSchemaSaleLineNestedPartial;
  notes: string;
  date_order?: string;
  origin: string;
};
export type GetFormField = {
  name: string;
  type: string;
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
        | 'partner_id'
        | 'company_id'
        | 'notes'
        | 'date_order'
        | 'origin'
      )
    | SchemaGetFieldRelationInput
  )[];
};
export type SaleUpdate = {
};
export type SaleUpdate2 = {
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
        | 'partner_id'
        | 'company_id'
        | 'notes'
        | 'date_order'
        | 'origin'
      )
    | SchemaGetFieldRelationInput2
  )[];
};
export type SaleLineReadSearchOutput = {
};
export type SchemaSearchOutputListSaleLineReadSearchOutput = {
  data: SaleLineReadSearchOutput[];
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
};
export type SchemaProductNestedPartial = {
};
export type SchemaUomNestedPartial = {
};
export type SchemaTaxNestedPartial = {
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
