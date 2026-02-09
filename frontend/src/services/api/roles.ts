/**
 * roles.ts — types only (codegen hooks removed, CRUD via generic crudApi.ts)
 */

export type SchemaRole = {
  id: number;
  name?: string | null;
  app_id?: any;
  active?: boolean | null;
};
