/**
 * partner.ts — types only (codegen hooks removed, CRUD via generic crudApi.ts)
 */
export type Partner = {
  id: number;
  name: string;
  active?: boolean;
  parent_id: SchemaPartnerNestedPartial;
  child_ids: SchemaSearchOutputListSchemaPartnerNestedPartial;
  user_id: SchemaUserNestedPartial;
  company_id: SchemaCompanyNestedPartial;
  tz?: string;
  lang?: string;
  vat: string;
  notes: string;
  website: string;
  email: string;
  phone: string;
  mobile: string;
};
