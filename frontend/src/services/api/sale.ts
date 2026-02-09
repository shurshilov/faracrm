/**
 * sale.ts — types only (codegen hooks removed, CRUD via generic crudApi.ts)
 */
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
