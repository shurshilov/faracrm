import { crudApi as api } from './crudApi';
const injectedRtkApi = api.injectEndpoints({
  endpoints: build => ({
    routeLeadSearchPost: build.mutation<
      RouteLeadSearchPostApiResponse,
      RouteLeadSearchPostApiArg
    >({
      query: queryArg => ({
        url: `/lead/search`,
        method: 'POST',
        body: queryArg.leadSearchInput,
      }),
    }),
    routeLeadSearchMany2ManyGet: build.query<
      RouteLeadSearchMany2ManyGetApiResponse,
      RouteLeadSearchMany2ManyGetApiArg
    >({
      query: queryArg => ({
        url: `/lead/search_many2many`,
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
    routeLeadPost: build.mutation<
      RouteLeadPostApiResponse,
      RouteLeadPostApiArg
    >({
      query: queryArg => ({
        url: `/lead`,
        method: 'POST',
        body: queryArg.leadCreate,
      }),
    }),
    routeLeadDefaultValuesPost: build.mutation<
      RouteLeadDefaultValuesPostApiResponse,
      RouteLeadDefaultValuesPostApiArg
    >({
      query: queryArg => ({
        url: `/lead/default_values`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput11,
      }),
    }),
    routeLeadIdPut: build.mutation<
      RouteLeadIdPutApiResponse,
      RouteLeadIdPutApiArg
    >({
      query: queryArg => ({
        url: `/lead/${queryArg.id}`,
        method: 'PUT',
        body: queryArg.leadUpdate,
      }),
    }),
    routeLeadIdDelete: build.mutation<
      RouteLeadIdDeleteApiResponse,
      RouteLeadIdDeleteApiArg
    >({
      query: queryArg => ({ url: `/lead/${queryArg.id}`, method: 'DELETE' }),
    }),
    routeLeadIdPost: build.mutation<
      RouteLeadIdPostApiResponse,
      RouteLeadIdPostApiArg
    >({
      query: queryArg => ({
        url: `/lead/${queryArg.id}`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput12,
      }),
    }),
    routeLeadBulkDelete: build.mutation<
      RouteLeadBulkDeleteApiResponse,
      RouteLeadBulkDeleteApiArg
    >({
      query: queryArg => ({
        url: `/lead/bulk`,
        method: 'DELETE',
        body: queryArg.ids,
      }),
    }),
  }),
  overrideExisting: false,
});
export { injectedRtkApi as crudApi };
export type RouteLeadSearchPostApiResponse =
  /** status 200 успешно */ SchemaSearchOutputListLeadReadSearchOutput;
export type RouteLeadSearchPostApiArg = {
  leadSearchInput: LeadSearchInput;
};
export type RouteLeadSearchMany2ManyGetApiResponse =
  /** status 200 успешно */ any;
export type RouteLeadSearchMany2ManyGetApiArg = {
  id: number;
  name: null;
  fields: string[];
  order?: 'desc' | 'asc';
  start?: number | null;
  end?: number | null;
  sort?: string;
  limit?: number;
};
export type RouteLeadPostApiResponse =
  /** status 200 успешно */ SchemaCreateOutput;
export type RouteLeadPostApiArg = {
  leadCreate: LeadCreate;
};
export type RouteLeadDefaultValuesPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputLead;
export type RouteLeadDefaultValuesPostApiArg = {
  backendBaseSystemDotormDotormUtilsSchemaGetInput11: SchemaGetInput;
};
export type RouteLeadIdPutApiResponse = /** status 200 успешно */ LeadUpdate;
export type RouteLeadIdPutApiArg = {
  id: number;
  leadUpdate: LeadUpdate;
};
export type RouteLeadIdDeleteApiResponse = /** status 200 успешно */ true;
export type RouteLeadIdDeleteApiArg = {
  id: number;
};
export type RouteLeadIdPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputLead;
export type RouteLeadIdPostApiArg = {
  id: number;
  backendBaseSystemDotormDotormUtilsSchemaGetInput12: SchemaGetInput2;
};
export type RouteLeadBulkDeleteApiResponse = /** status 200 успешно */ true;
export type RouteLeadBulkDeleteApiArg = {
  ids: number[];
};
export type SchemaRelationNested = {
  id: number;
  name: string;
};
export type LeadReadSearchOutput = {
  id?: number | null;
  name?: string | null;
  active?: boolean | null;
  user_id?: SchemaRelationNested | null;
  parent_id?: SchemaRelationNested | null;
  company_id?: SchemaRelationNested | null;
  notes?: string | null;
  type?: string | null;
  website?: string | null;
  email?: string | null;
  phone?: string | null;
  mobile?: string | null;
};
export type GetListField = {
  name: string;
  type: string;
  relation?: string | null;
};
export type SchemaSearchOutputListLeadReadSearchOutput = {
  data: LeadReadSearchOutput[];
  total?: number | null;
  fields: GetListField[];
};
export type LeadSearchInput = {
  fields: (
    | 'id'
    | 'name'
    | 'active'
    | 'user_id'
    | 'parent_id'
    | 'company_id'
    | 'notes'
    | 'type'
    | 'website'
    | 'email'
    | 'phone'
    | 'mobile'
  )[];
  end?: number | null;
  order?: 'DESC' | 'ASC' | 'desc' | 'asc';
  sort?:
    | 'id'
    | 'name'
    | 'active'
    | 'user_id'
    | 'parent_id'
    | 'company_id'
    | 'notes'
    | 'type'
    | 'website'
    | 'email'
    | 'phone'
    | 'mobile';
  start?: number | null;
  limit?: number;
  filter?: (
    | ['id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | [
        'name',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | ['active', '=' | '!=', boolean]
    | ['user_id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['parent_id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['company_id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | [
        'notes',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | [
        'type',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | [
        'website',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | [
        'email',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | [
        'phone',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | [
        'mobile',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
  )[];
  raw?: boolean;
};
export type SchemaCreateOutput = {
  id: number;
};
export type LeadCreate = {
  name: string;
  active?: boolean;
  user_id: number | 'VirtualId';
  parent_id: number | 'VirtualId';
  company_id: number | 'VirtualId';
  notes: string;
  type?: string;
  website: string;
  email: string;
  phone: string;
  mobile: string;
};
export type SchemaUserNestedPartial = {
  id?: number | null;
  name?: string | null;
  login?: string | null;
  email?: string | null;
  password_hash?: string | null;
  password_salt?: string | null;
  image?: SchemaRelationNested | null;
  image_ids?: SchemaRelationNested[] | null;
  role_ids?: SchemaRelationNested[] | null;
};
export type SchemaPartnerNestedPartial = {
  id?: number | null;
  name?: string | null;
  active?: boolean | null;
  parent_id?: SchemaRelationNested | null;
  child_ids?: SchemaRelationNested[] | null;
  user_id?: SchemaRelationNested | null;
  company_id?: SchemaRelationNested | null;
  tz?: string | null;
  lang?: string | null;
  vat?: string | null;
  notes?: string | null;
  website?: string | null;
  email?: string | null;
  phone?: string | null;
  mobile?: string | null;
};
export type SchemaCompanyNestedPartial = {
  id?: number | null;
  name?: string | null;
  active?: boolean | null;
  sequence?: number | null;
  parent_id?: SchemaRelationNested | null;
  child_ids?: SchemaRelationNested[] | null;
};
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
export type GetFormField = {
  name: string;
  type: string;
  relatedModel?: string | null;
  relatedField?: string | null;
  options?: any[] | null;
};
export type SchemaGetOutputLead = {
  data: Lead;
  fields: {
    [key: string]: GetFormField;
  };
};
export type SchemaGetInput = {
  fields: (
    | 'id'
    | 'name'
    | 'active'
    | 'user_id'
    | 'parent_id'
    | 'company_id'
    | 'notes'
    | 'type'
    | 'website'
    | 'email'
    | 'phone'
    | 'mobile'
  )[];
};
export type LeadUpdate = {
  name?: string | null;
  active?: boolean | null;
  user_id?: number | 'VirtualId' | null;
  parent_id?: number | 'VirtualId' | null;
  company_id?: number | 'VirtualId' | null;
  notes?: string | null;
  type?: string | null;
  website?: string | null;
  email?: string | null;
  phone?: string | null;
  mobile?: string | null;
};
export type SchemaGetInput2 = {
  fields: (
    | 'id'
    | 'name'
    | 'active'
    | 'user_id'
    | 'parent_id'
    | 'company_id'
    | 'notes'
    | 'type'
    | 'website'
    | 'email'
    | 'phone'
    | 'mobile'
  )[];
};
export const {
  useRouteLeadSearchPostMutation,
  useRouteLeadSearchMany2ManyGetQuery,
  useLazyRouteLeadSearchMany2ManyGetQuery,
  useRouteLeadPostMutation,
  useRouteLeadDefaultValuesPostMutation,
  useRouteLeadIdPutMutation,
  useRouteLeadIdDeleteMutation,
  useRouteLeadIdPostMutation,
  useRouteLeadBulkDeleteMutation,
} = injectedRtkApi;
