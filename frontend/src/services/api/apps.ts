/**
 * apps.ts — types only (codegen hooks removed, CRUD via generic crudApi.ts)
 */
export type SchemaApp = {
  id: number;
  code?: string | null;
  name?: string | null;
  active?: boolean | null;
};
