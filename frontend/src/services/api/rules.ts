/**
 * rules.ts — types only (codegen hooks removed, CRUD via generic crudApi.ts)
 */

export type SchemaRule = {
  id: number;
  name?: string | null;
  role_id?: any;
  model_id?: any;
  can_read?: boolean | null;
  can_write?: boolean | null;
  can_create?: boolean | null;
  can_delete?: boolean | null;
};
