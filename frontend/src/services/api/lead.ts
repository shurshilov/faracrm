/**
 * lead.ts — types only (codegen hooks removed, CRUD via generic crudApi.ts)
 */
export type Lead = {
  id: number;
  name: string;
  active?: boolean;
  user_id: SchemaUserNestedPartial;
  parent_id: SchemaPartnerNestedPartial;
  company_id: SchemaCompanyNestedPartial;
  notes: string;
  type?: string;
  website: string;
  email: string;
  phone: string;
  mobile: string;
};
