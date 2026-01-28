import { crudApi as api } from './crudApi';
const injectedRtkApi = api.injectEndpoints({
  endpoints: build => ({
    routeRulesSearchPost: build.mutation<
      RouteRulesSearchPostApiResponse,
      RouteRulesSearchPostApiArg
    >({
      query: queryArg => ({
        url: `/rules/search`,
        method: 'POST',
        body: queryArg.ruleSearchInput,
      }),
    }),
    routeRulesSearchMany2ManyGet: build.query<
      RouteRulesSearchMany2ManyGetApiResponse,
      RouteRulesSearchMany2ManyGetApiArg
    >({
      query: queryArg => ({
        url: `/rules/search_many2many`,
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
    routeRulesPost: build.mutation<
      RouteRulesPostApiResponse,
      RouteRulesPostApiArg
    >({
      query: queryArg => ({
        url: `/rules`,
        method: 'POST',
        body: queryArg.ruleCreate,
      }),
    }),
    routeRulesDefaultValuesPost: build.mutation<
      RouteRulesDefaultValuesPostApiResponse,
      RouteRulesDefaultValuesPostApiArg
    >({
      query: queryArg => ({
        url: `/rules/default_values`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput21,
      }),
    }),
    routeRulesIdPut: build.mutation<
      RouteRulesIdPutApiResponse,
      RouteRulesIdPutApiArg
    >({
      query: queryArg => ({
        url: `/rules/${queryArg.id}`,
        method: 'PUT',
        body: queryArg.ruleUpdate,
      }),
    }),
    routeRulesIdDelete: build.mutation<
      RouteRulesIdDeleteApiResponse,
      RouteRulesIdDeleteApiArg
    >({
      query: queryArg => ({ url: `/rules/${queryArg.id}`, method: 'DELETE' }),
    }),
    routeRulesIdPost: build.mutation<
      RouteRulesIdPostApiResponse,
      RouteRulesIdPostApiArg
    >({
      query: queryArg => ({
        url: `/rules/${queryArg.id}`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput22,
      }),
    }),
    routeRulesBulkDelete: build.mutation<
      RouteRulesBulkDeleteApiResponse,
      RouteRulesBulkDeleteApiArg
    >({
      query: queryArg => ({
        url: `/rules/bulk`,
        method: 'DELETE',
        body: queryArg.ids,
      }),
    }),
  }),
  overrideExisting: false,
});
export { injectedRtkApi as crudApi };
export type RouteRulesSearchPostApiResponse =
  /** status 200 успешно */ SchemaSearchOutputListRuleReadSearchOutput;
export type RouteRulesSearchPostApiArg = {
  ruleSearchInput: RuleSearchInput;
};
export type RouteRulesSearchMany2ManyGetApiResponse =
  /** status 200 успешно */ any;
export type RouteRulesSearchMany2ManyGetApiArg = {
  id: number;
  name: null;
  fields: string[];
  order?: 'desc' | 'asc';
  start?: number | null;
  end?: number | null;
  sort?: string;
  limit?: number;
};
export type RouteRulesPostApiResponse =
  /** status 200 успешно */ SchemaCreateOutput;
export type RouteRulesPostApiArg = {
  ruleCreate: RuleCreate;
};
export type RouteRulesDefaultValuesPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputRule;
export type RouteRulesDefaultValuesPostApiArg = {
  backendBaseSystemDotormDotormUtilsSchemaGetInput21: SchemaGetInput;
};
export type RouteRulesIdPutApiResponse = /** status 200 успешно */ RuleUpdate;
export type RouteRulesIdPutApiArg = {
  id: number;
  ruleUpdate: RuleUpdate;
};
export type RouteRulesIdDeleteApiResponse = /** status 200 успешно */ true;
export type RouteRulesIdDeleteApiArg = {
  id: number;
};
export type RouteRulesIdPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputRule;
export type RouteRulesIdPostApiArg = {
  id: number;
  backendBaseSystemDotormDotormUtilsSchemaGetInput22: SchemaGetInput2;
};
export type RouteRulesBulkDeleteApiResponse = /** status 200 успешно */ true;
export type RouteRulesBulkDeleteApiArg = {
  ids: number[];
};
export type SchemaRelationNested = {
  id: number;
  name: string;
};
export type RuleReadSearchOutput = {
  id?: number | null;
  name?: string | null;
  role_id?: SchemaRelationNested | null;
};
export type GetListField = {
  name: string;
  type: string;
  relation?: string | null;
};
export type SchemaSearchOutputListRuleReadSearchOutput = {
  data: RuleReadSearchOutput[];
  total?: number | null;
  fields: GetListField[];
};
export type RuleSearchInput = {
  fields: ('id' | 'name' | 'role_id')[];
  end?: number | null;
  order?: 'DESC' | 'ASC' | 'desc' | 'asc';
  sort?: 'id' | 'name' | 'role_id';
  start?: number | null;
  limit?: number;
  filter?: (
    | ['id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | [
        'name',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | ['role_id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
  )[];
  raw?: boolean;
};
export type SchemaCreateOutput = {
  id: number;
};
export type RuleCreate = {
  name: string;
  role_id: number | 'VirtualId';
};
export type SchemaRoleNestedPartial = {
  id?: number | null;
  name?: string | null;
  model_id?: SchemaRelationNested | null;
  user_ids?: SchemaRelationNested[] | null;
  acl_ids?: SchemaRelationNested[] | null;
  rule_ids?: SchemaRelationNested[] | null;
};
export type Rule = {
  id: number;
  name: string;
  role_id: SchemaRoleNestedPartial;
};
export type GetFormField = {
  name: string;
  type: string;
  relatedModel?: string | null;
  relatedField?: string | null;
  options?: any[] | null;
};
export type SchemaGetOutputRule = {
  data: Rule;
  fields: {
    [key: string]: GetFormField;
  };
};
export type SchemaGetInput = {
  fields: ('id' | 'name' | 'role_id')[];
};
export type RuleUpdate = {
  name?: string | null;
  role_id?: number | 'VirtualId' | null;
};
export type SchemaGetInput2 = {
  fields: ('id' | 'name' | 'role_id')[];
};
export const {
  useRouteRulesSearchPostMutation,
  useRouteRulesSearchMany2ManyGetQuery,
  useLazyRouteRulesSearchMany2ManyGetQuery,
  useRouteRulesPostMutation,
  useRouteRulesDefaultValuesPostMutation,
  useRouteRulesIdPutMutation,
  useRouteRulesIdDeleteMutation,
  useRouteRulesIdPostMutation,
  useRouteRulesBulkDeleteMutation,
} = injectedRtkApi;
