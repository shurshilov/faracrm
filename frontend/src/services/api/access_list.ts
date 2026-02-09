/**
 * access_list.ts — types only (codegen hooks removed, CRUD via generic crudApi.ts)
 */

export type SchemaAccessList = {
  id?: number | null;
  name?: string | null;
  model_id?: any;
  role_id?: any;
  domain?: string | null;
};

export type SchemaModel = {
  id?: number | null;
  name?: string | null;
  model?: string | null;
};
