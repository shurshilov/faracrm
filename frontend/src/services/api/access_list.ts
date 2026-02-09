/**
 * access_list.ts — types only (codegen hooks removed, CRUD via generic crudApi.ts)
 */

export type SchemaAccessList = {
  id: number;
  name?: string | null;
  model_id?: any;
  role_id?: any;
  domain?: string | null;
};

export type SchemaModel = {
  id: number;
  name: string;
  model?: string | null;
};
