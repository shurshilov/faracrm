import { crudApi as api } from './crudApi';
const injectedRtkApi = api.injectEndpoints({
  endpoints: build => ({
    routePartnersSearchPost: build.mutation<
      RoutePartnersSearchPostApiResponse,
      RoutePartnersSearchPostApiArg
    >({
      query: queryArg => ({
        url: `/partners/search`,
        method: 'POST',
        body: queryArg.partnerSearchInput,
      }),
    }),
    routePartnersSearchMany2ManyGet: build.query<
      RoutePartnersSearchMany2ManyGetApiResponse,
      RoutePartnersSearchMany2ManyGetApiArg
    >({
      query: queryArg => ({
        url: `/partners/search_many2many`,
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
    routePartnersPost: build.mutation<
      RoutePartnersPostApiResponse,
      RoutePartnersPostApiArg
    >({
      query: queryArg => ({
        url: `/partners`,
        method: 'POST',
        body: queryArg.partnerCreate,
      }),
    }),
    routePartnersDefaultValuesPost: build.mutation<
      RoutePartnersDefaultValuesPostApiResponse,
      RoutePartnersDefaultValuesPostApiArg
    >({
      query: queryArg => ({
        url: `/partners/default_values`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput15,
      }),
    }),
    routePartnersIdPut: build.mutation<
      RoutePartnersIdPutApiResponse,
      RoutePartnersIdPutApiArg
    >({
      query: queryArg => ({
        url: `/partners/${queryArg.id}`,
        method: 'PUT',
        body: queryArg.partnerUpdateInput,
      }),
    }),
    routePartnersIdDelete: build.mutation<
      RoutePartnersIdDeleteApiResponse,
      RoutePartnersIdDeleteApiArg
    >({
      query: queryArg => ({
        url: `/partners/${queryArg.id}`,
        method: 'DELETE',
      }),
    }),
    routePartnersIdPost: build.mutation<
      RoutePartnersIdPostApiResponse,
      RoutePartnersIdPostApiArg
    >({
      query: queryArg => ({
        url: `/partners/${queryArg.id}`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput16,
      }),
    }),
    routePartnersBulkDelete: build.mutation<
      RoutePartnersBulkDeleteApiResponse,
      RoutePartnersBulkDeleteApiArg
    >({
      query: queryArg => ({
        url: `/partners/bulk`,
        method: 'DELETE',
        body: queryArg.ids,
      }),
    }),
  }),
  overrideExisting: false,
});
export { injectedRtkApi as crudApi };
export type RoutePartnersSearchPostApiResponse =
  /** status 200 успешно */ SchemaSearchOutputListPartnerReadSearchOutput;
export type RoutePartnersSearchPostApiArg = {
  partnerSearchInput: PartnerSearchInput;
};
export type RoutePartnersSearchMany2ManyGetApiResponse =
  /** status 200 успешно */ any;
export type RoutePartnersSearchMany2ManyGetApiArg = {
  id: number;
  name: null;
  fields: string[];
  order?: 'desc' | 'asc';
  start?: number | null;
  end?: number | null;
  sort?: string;
  limit?: number;
};
export type RoutePartnersPostApiResponse =
  /** status 200 успешно */ SchemaCreateOutput;
export type RoutePartnersPostApiArg = {
  partnerCreate: PartnerCreate;
};
export type RoutePartnersDefaultValuesPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputPartner;
export type RoutePartnersDefaultValuesPostApiArg = {
  backendBaseSystemDotormDotormUtilsSchemaGetInput15: SchemaGetInput;
};
export type RoutePartnersIdPutApiResponse =
  /** status 200 успешно */ PartnerUpdate;
export type RoutePartnersIdPutApiArg = {
  id: number;
  partnerUpdateInput: PartnerUpdate2;
};
export type RoutePartnersIdDeleteApiResponse = /** status 200 успешно */ true;
export type RoutePartnersIdDeleteApiArg = {
  id: number;
};
export type RoutePartnersIdPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputPartner;
export type RoutePartnersIdPostApiArg = {
  id: number;
  backendBaseSystemDotormDotormUtilsSchemaGetInput16: SchemaGetInput2;
};
export type RoutePartnersBulkDeleteApiResponse = /** status 200 успешно */ true;
export type RoutePartnersBulkDeleteApiArg = {
  ids: number[];
};
export type SchemaRelationNested = {
  id: number;
  name: string;
};
export type PartnerReadSearchOutput = {
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
export type GetListField = {
  name: string;
  type: string;
  relation?: string | null;
};
export type SchemaSearchOutputListPartnerReadSearchOutput = {
  data: PartnerReadSearchOutput[];
  total?: number | null;
  fields: GetListField[];
};
export type PartnerSearchInput = {
  fields: (
    | 'id'
    | 'name'
    | 'active'
    | 'parent_id'
    | 'child_ids'
    | 'user_id'
    | 'company_id'
    | 'tz'
    | 'lang'
    | 'vat'
    | 'notes'
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
    | 'parent_id'
    | 'child_ids'
    | 'user_id'
    | 'company_id'
    | 'tz'
    | 'lang'
    | 'vat'
    | 'notes'
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
    | ['parent_id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['child_ids', 'in' | 'not in', number[]]
    | ['user_id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['company_id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | [
        'tz',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | [
        'lang',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | [
        'vat',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | [
        'notes',
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
export type SchemaAttachmentStorage = {
  id: number;
  name: string;
  type?: string;
};
export type SchemaAttachment = {
  id: number;
  name: string | null;
  res_model: string | null;
  res_field: string | null;
  res_id: number | null;
  public: boolean | null;
  folder: boolean | null;
  access_token: string | null;
  size: number | null;
  checksum: string | null;
  mimetype: string | null;
  storage_id: SchemaAttachmentStorage | null;
  storage_file_id: string | null;
  storage_parent_id: string | null;
  storage_parent_name: string | null;
  storage_file_url: string | null;
  content: Blob | null;
};
export type SchemaModel = {
  id: number;
  name: string;
};
export type SchemaAccessList = {
  id: number;
  active?: boolean;
  name: string;
  model_id: SchemaModel | null;
  role_id: SchemaRole | null;
  perm_create: boolean;
  perm_read: boolean;
  perm_update: boolean;
  perm_delete: boolean;
};
export type SchemaRule = {
  id: number;
  name: string;
  role_id: SchemaRole | null;
};
export type SchemaRole = {
  id: number;
  name: string;
  model_id: SchemaModel | null;
  user_ids: SchemaUser[] | null;
  acl_ids: SchemaAccessList[] | null;
  rule_ids: SchemaRule[] | null;
};
export type SchemaUser = {
  id: number;
  name: string;
  login: string | null;
  email: string;
  password_hash: string | null;
  password_salt: string | null;
  image: SchemaAttachment | null;
  image_ids: SchemaAttachment[] | null;
  role_ids: SchemaRole[] | null;
};
export type SchemaCompany = {
  id: number;
  name: string;
  active?: boolean;
  sequence?: number;
  parent_id: SchemaCompany;
  child_ids: SchemaCompany[];
};
export type SchemaPartner = {
  id: number;
  name: string;
  active?: boolean;
  parent_id: SchemaPartner;
  child_ids: SchemaPartner[];
  user_id: SchemaUser;
  company_id: SchemaCompany;
  tz?: string;
  lang?: string;
  vat: string;
  notes: string;
  website: string;
  email: string;
  phone: string;
  mobile: string;
};
export type SchemaPartnerRelationNestedCreate = {
  name?: string | null;
  active?: boolean | null;
  parent_id?: SchemaPartner | null;
  user_id?: SchemaUser | null;
  company_id?: SchemaCompany | null;
  tz?: string | null;
  lang?: string | null;
  vat?: string | null;
  notes?: string | null;
  website?: string | null;
  email?: string | null;
  phone?: string | null;
  mobile?: string | null;
};
export type SchemaRelationOne2ManyUpdateCreateSchemaPartnerRelationNestedCreate =
  {
    created?: SchemaPartnerRelationNestedCreate[];
    deleted?: number[];
  };
export type SchemaPartnerRelationNestedUpdate = {
  name?: string | null;
  active?: boolean | null;
  parent_id?: number | 'VirtualId' | null;
  child_ids?: SchemaRelationOne2ManyUpdateCreateSchemaPartnerRelationNestedCreate | null;
  user_id?: number | 'VirtualId' | null;
  company_id?: number | 'VirtualId' | null;
  tz?: string | null;
  lang?: string | null;
  vat?: string | null;
  notes?: string | null;
  website?: string | null;
  email?: string | null;
  phone?: string | null;
  mobile?: string | null;
};
export type SchemaRelationOne2ManyUpdateCreateSchemaPartnerRelationNestedUpdate =
  {
    created?: SchemaPartnerRelationNestedUpdate[];
    deleted?: number[];
  };
export type PartnerCreate = {
  name: string;
  active?: boolean;
  parent_id: number | 'VirtualId';
  child_ids: SchemaRelationOne2ManyUpdateCreateSchemaPartnerRelationNestedUpdate;
  user_id: number | 'VirtualId';
  company_id: number | 'VirtualId';
  tz?: string;
  lang?: string;
  vat: string;
  notes: string;
  website: string;
  email: string;
  phone: string;
  mobile: string;
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
export type SchemaSearchOutputListSchemaPartnerNestedPartial = {
  data: SchemaPartnerNestedPartial[];
  total?: number | null;
  fields: GetListField[];
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
export type SchemaCompanyNestedPartial = {
  id?: number | null;
  name?: string | null;
  active?: boolean | null;
  sequence?: number | null;
  parent_id?: SchemaRelationNested | null;
  child_ids?: SchemaRelationNested[] | null;
};
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
export type GetFormField = {
  name: string;
  type: string;
  relatedModel?: string | null;
  relatedField?: string | null;
  options?: any[] | null;
};
export type SchemaGetOutputPartner = {
  data: Partner;
  fields: {
    [key: string]: GetFormField;
  };
};
export type SchemaGetFieldRelationInput = {
  child_ids: (
    | 'id'
    | 'name'
    | 'active'
    | 'parent_id'
    | 'child_ids'
    | 'user_id'
    | 'company_id'
    | 'tz'
    | 'lang'
    | 'vat'
    | 'notes'
    | 'website'
    | 'email'
    | 'phone'
    | 'mobile'
  )[];
};
export type SchemaGetInput = {
  fields: (
    | (
        | 'id'
        | 'name'
        | 'active'
        | 'parent_id'
        | 'user_id'
        | 'company_id'
        | 'tz'
        | 'lang'
        | 'vat'
        | 'notes'
        | 'website'
        | 'email'
        | 'phone'
        | 'mobile'
      )
    | SchemaGetFieldRelationInput
  )[];
};
export type SchemaAccessList2 = {
  id: number;
  active?: boolean;
  name: string;
  model_id: SchemaModel | null;
  role_id: SchemaRole2 | null;
  perm_create: boolean;
  perm_read: boolean;
  perm_update: boolean;
  perm_delete: boolean;
};
export type SchemaRule2 = {
  id: number;
  name: string;
  role_id: SchemaRole2 | null;
};
export type SchemaRole2 = {
  id: number;
  name: string;
  model_id: SchemaModel | null;
  user_ids: SchemaUser2[] | null;
  acl_ids: SchemaAccessList2[] | null;
  rule_ids: SchemaRule2[] | null;
};
export type SchemaUser2 = {
  id: number;
  name: string;
  login: string | null;
  email: string;
  password_hash: string | null;
  password_salt: string | null;
  image: SchemaAttachment | null;
  image_ids: SchemaAttachment[] | null;
  role_ids: SchemaRole2[] | null;
};
export type SchemaCompany2 = {
  id: number;
  name: string;
  active?: boolean;
  sequence?: number;
  parent_id: SchemaCompany2;
  child_ids: SchemaCompany2[];
};
export type SchemaPartner2 = {
  id: number;
  name: string;
  active?: boolean;
  parent_id: SchemaPartner2;
  child_ids: SchemaPartner2[];
  user_id: SchemaUser2;
  company_id: SchemaCompany2;
  tz?: string;
  lang?: string;
  vat: string;
  notes: string;
  website: string;
  email: string;
  phone: string;
  mobile: string;
};
export type SchemaPartnerRelationNestedCreate2 = {
  name?: string | null;
  active?: boolean | null;
  parent_id?: SchemaPartner2 | null;
  user_id?: SchemaUser2 | null;
  company_id?: SchemaCompany2 | null;
  tz?: string | null;
  lang?: string | null;
  vat?: string | null;
  notes?: string | null;
  website?: string | null;
  email?: string | null;
  phone?: string | null;
  mobile?: string | null;
};
export type SchemaRelationOne2ManyUpdateCreateSchemaPartnerRelationNestedCreate2 =
  {
    created?: SchemaPartnerRelationNestedCreate2[];
    deleted?: number[];
  };
export type SchemaPartnerRelationNestedUpdate2 = {
  name?: string | null;
  active?: boolean | null;
  parent_id?: number | 'VirtualId' | null;
  child_ids?: SchemaRelationOne2ManyUpdateCreateSchemaPartnerRelationNestedCreate2 | null;
  user_id?: number | 'VirtualId' | null;
  company_id?: number | 'VirtualId' | null;
  tz?: string | null;
  lang?: string | null;
  vat?: string | null;
  notes?: string | null;
  website?: string | null;
  email?: string | null;
  phone?: string | null;
  mobile?: string | null;
};
export type SchemaRelationOne2ManyUpdateCreateSchemaPartnerRelationNestedUpdate2 =
  {
    created?: SchemaPartnerRelationNestedUpdate2[];
    deleted?: number[];
  };
export type PartnerUpdate = {
  name?: string | null;
  active?: boolean | null;
  parent_id?: number | 'VirtualId' | null;
  child_ids?: SchemaRelationOne2ManyUpdateCreateSchemaPartnerRelationNestedUpdate2 | null;
  user_id?: number | 'VirtualId' | null;
  company_id?: number | 'VirtualId' | null;
  tz?: string | null;
  lang?: string | null;
  vat?: string | null;
  notes?: string | null;
  website?: string | null;
  email?: string | null;
  phone?: string | null;
  mobile?: string | null;
};
export type SchemaPartnerRelationNestedUpdate3 = {
  name?: string | null;
  active?: boolean | null;
  parent_id?: number | 'VirtualId' | null;
  child_ids?: SchemaRelationOne2ManyUpdateCreateSchemaPartnerRelationNestedCreate | null;
  user_id?: number | 'VirtualId' | null;
  company_id?: number | 'VirtualId' | null;
  tz?: string | null;
  lang?: string | null;
  vat?: string | null;
  notes?: string | null;
  website?: string | null;
  email?: string | null;
  phone?: string | null;
  mobile?: string | null;
};
export type SchemaRelationOne2ManyUpdateCreateSchemaPartnerRelationNestedUpdate3 =
  {
    created?: SchemaPartnerRelationNestedUpdate3[];
    deleted?: number[];
  };
export type PartnerUpdate2 = {
  name?: string | null;
  active?: boolean | null;
  parent_id?: number | 'VirtualId' | null;
  child_ids?: SchemaRelationOne2ManyUpdateCreateSchemaPartnerRelationNestedUpdate3 | null;
  user_id?: number | 'VirtualId' | null;
  company_id?: number | 'VirtualId' | null;
  tz?: string | null;
  lang?: string | null;
  vat?: string | null;
  notes?: string | null;
  website?: string | null;
  email?: string | null;
  phone?: string | null;
  mobile?: string | null;
};
export type SchemaGetFieldRelationInput2 = {
  child_ids: (
    | 'id'
    | 'name'
    | 'active'
    | 'parent_id'
    | 'child_ids'
    | 'user_id'
    | 'company_id'
    | 'tz'
    | 'lang'
    | 'vat'
    | 'notes'
    | 'website'
    | 'email'
    | 'phone'
    | 'mobile'
  )[];
};
export type SchemaGetInput2 = {
  fields: (
    | (
        | 'id'
        | 'name'
        | 'active'
        | 'parent_id'
        | 'user_id'
        | 'company_id'
        | 'tz'
        | 'lang'
        | 'vat'
        | 'notes'
        | 'website'
        | 'email'
        | 'phone'
        | 'mobile'
      )
    | SchemaGetFieldRelationInput2
  )[];
};
export const {
  useRoutePartnersSearchPostMutation,
  useRoutePartnersSearchMany2ManyGetQuery,
  useLazyRoutePartnersSearchMany2ManyGetQuery,
  useRoutePartnersPostMutation,
  useRoutePartnersDefaultValuesPostMutation,
  useRoutePartnersIdPutMutation,
  useRoutePartnersIdDeleteMutation,
  useRoutePartnersIdPostMutation,
  useRoutePartnersBulkDeleteMutation,
} = injectedRtkApi;
