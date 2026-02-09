/**
 * product.ts — types only (codegen hooks removed, CRUD via generic crudApi.ts)
 */
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
