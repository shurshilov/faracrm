import { crudApi as api } from './crudApi';
const injectedRtkApi = api.injectEndpoints({
  endpoints: build => ({
    routeRolesSearchPost: build.mutation<
      RouteRolesSearchPostApiResponse,
      RouteRolesSearchPostApiArg
    >({
      query: queryArg => ({
        url: `/roles/search`,
        method: 'POST',
        body: queryArg.roleSearchInput,
      }),
    }),
    routeRolesSearchMany2ManyGet: build.query<
      RouteRolesSearchMany2ManyGetApiResponse,
      RouteRolesSearchMany2ManyGetApiArg
    >({
      query: queryArg => ({
        url: `/roles/search_many2many`,
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
    routeRolesPost: build.mutation<
      RouteRolesPostApiResponse,
      RouteRolesPostApiArg
    >({
      query: queryArg => ({
        url: `/roles`,
        method: 'POST',
        body: queryArg.roleCreate,
      }),
    }),
    routeRolesDefaultValuesPost: build.mutation<
      RouteRolesDefaultValuesPostApiResponse,
      RouteRolesDefaultValuesPostApiArg
    >({
      query: queryArg => ({
        url: `/roles/default_values`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput19,
      }),
    }),
    routeRolesIdPut: build.mutation<
      RouteRolesIdPutApiResponse,
      RouteRolesIdPutApiArg
    >({
      query: queryArg => ({
        url: `/roles/${queryArg.id}`,
        method: 'PUT',
        body: queryArg.roleUpdateInput,
      }),
    }),
    routeRolesIdDelete: build.mutation<
      RouteRolesIdDeleteApiResponse,
      RouteRolesIdDeleteApiArg
    >({
      query: queryArg => ({ url: `/roles/${queryArg.id}`, method: 'DELETE' }),
    }),
    routeRolesIdPost: build.mutation<
      RouteRolesIdPostApiResponse,
      RouteRolesIdPostApiArg
    >({
      query: queryArg => ({
        url: `/roles/${queryArg.id}`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput20,
      }),
    }),
    routeRolesBulkDelete: build.mutation<
      RouteRolesBulkDeleteApiResponse,
      RouteRolesBulkDeleteApiArg
    >({
      query: queryArg => ({
        url: `/roles/bulk`,
        method: 'DELETE',
        body: queryArg.ids,
      }),
    }),
  }),
  overrideExisting: false,
});
export { injectedRtkApi as crudApi };
export type RouteRolesSearchPostApiResponse =
  /** status 200 успешно */ SchemaSearchOutputListRoleReadSearchOutput;
export type RouteRolesSearchPostApiArg = {
  roleSearchInput: RoleSearchInput;
};
export type RouteRolesSearchMany2ManyGetApiResponse =
  /** status 200 успешно */ any;
export type RouteRolesSearchMany2ManyGetApiArg = {
  id: number;
  name: 'user_ids';
  fields: string[];
  order?: 'desc' | 'asc';
  start?: number | null;
  end?: number | null;
  sort?: string;
  limit?: number;
};
export type RouteRolesPostApiResponse =
  /** status 200 успешно */ SchemaCreateOutput;
export type RouteRolesPostApiArg = {
  roleCreate: RoleCreate;
};
export type RouteRolesDefaultValuesPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputRole;
export type RouteRolesDefaultValuesPostApiArg = {
  backendBaseSystemDotormDotormUtilsSchemaGetInput19: SchemaGetInput;
};
export type RouteRolesIdPutApiResponse = /** status 200 успешно */ RoleUpdate;
export type RouteRolesIdPutApiArg = {
  id: number;
  roleUpdateInput: RoleUpdate2;
};
export type RouteRolesIdDeleteApiResponse = /** status 200 успешно */ true;
export type RouteRolesIdDeleteApiArg = {
  id: number;
};
export type RouteRolesIdPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputRole;
export type RouteRolesIdPostApiArg = {
  id: number;
  backendBaseSystemDotormDotormUtilsSchemaGetInput20: SchemaGetInput2;
};
export type RouteRolesBulkDeleteApiResponse = /** status 200 успешно */ true;
export type RouteRolesBulkDeleteApiArg = {
  ids: number[];
};
export type SchemaRelationNested = {
  id: number;
  name: string;
};
export type RoleReadSearchOutput = {
  id?: number | null;
  name?: string | null;
  model_id?: SchemaRelationNested | null;
  user_ids?: SchemaRelationNested[] | null;
  acl_ids?: SchemaRelationNested[] | null;
  rule_ids?: SchemaRelationNested[] | null;
};
export type GetListField = {
  name: string;
  type: string;
  relation?: string | null;
};
export type SchemaSearchOutputListRoleReadSearchOutput = {
  data: RoleReadSearchOutput[];
  total?: number | null;
  fields: GetListField[];
};
export type RoleSearchInput = {
  fields: ('id' | 'name' | 'model_id' | 'user_ids' | 'acl_ids' | 'rule_ids')[];
  end?: number | null;
  order?: 'DESC' | 'ASC' | 'desc' | 'asc';
  sort?: 'id' | 'name' | 'model_id' | 'user_ids' | 'acl_ids' | 'rule_ids';
  start?: number | null;
  limit?: number;
  filter?: (
    | ['id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | [
        'name',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | ['model_id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['user_ids', 'in' | 'not in', number[]]
    | ['acl_ids', 'in' | 'not in', number[]]
    | ['rule_ids', 'in' | 'not in', number[]]
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
export type SchemaAttachmentRelationNestedCreate = {
  name?: string | null;
  res_model?: string | null;
  res_field?: string | null;
  res_id?: number | null;
  public?: boolean | null;
  folder?: boolean | null;
  access_token?: string | null;
  size?: number | null;
  checksum?: string | null;
  mimetype?: string | null;
  storage_id?: SchemaAttachmentStorage | null;
  storage_file_id?: string | null;
  storage_parent_id?: string | null;
  storage_parent_name?: string | null;
  storage_file_url?: string | null;
  content?: Blob | null;
};
export type SchemaRelationOne2ManyUpdateCreateSchemaAttachmentRelationNestedCreate =
  {
    created?: SchemaAttachmentRelationNestedCreate[];
    deleted?: number[];
  };
export type SchemaModel = {
  id: number;
  name: string;
};
export type SchemaRoleRelationNestedCreate = {
  name?: string | null;
  model_id?: SchemaModel | null;
};
export type SchemaRelationMany2ManyUpdateCreateSchemaRoleRelationNestedCreate =
  {
    created?: SchemaRoleRelationNestedCreate[];
    selected?: number[];
    unselected?: number[];
  };
export type SchemaUserRelationNestedUpdate = {
  name?: string | null;
  login?: string | null;
  email?: string | null;
  password_hash?: string | null;
  password_salt?: string | null;
  image?: number | 'VirtualId' | null;
  image_ids?: SchemaRelationOne2ManyUpdateCreateSchemaAttachmentRelationNestedCreate | null;
  role_ids?: SchemaRelationMany2ManyUpdateCreateSchemaRoleRelationNestedCreate | null;
};
export type SchemaRelationMany2ManyUpdateCreateSchemaUserRelationNestedUpdate =
  {
    created?: SchemaUserRelationNestedUpdate[];
    selected?: number[];
    unselected?: number[];
  };
export type SchemaAccessListRelationNestedUpdate = {
  active?: boolean | null;
  name?: string | null;
  model_id?: number | 'VirtualId' | null;
  role_id?: number | 'VirtualId' | null;
  perm_create?: boolean | null;
  perm_read?: boolean | null;
  perm_update?: boolean | null;
  perm_delete?: boolean | null;
};
export type SchemaRelationOne2ManyUpdateCreateSchemaAccessListRelationNestedUpdate =
  {
    created?: SchemaAccessListRelationNestedUpdate[];
    deleted?: number[];
  };
export type SchemaRuleRelationNestedUpdate = {
  name?: string | null;
  role_id?: number | 'VirtualId' | null;
};
export type SchemaRelationOne2ManyUpdateCreateSchemaRuleRelationNestedUpdate = {
  created?: SchemaRuleRelationNestedUpdate[];
  deleted?: number[];
};
export type RoleCreate = {
  name: string;
  model_id: number | 'VirtualId';
  user_ids: SchemaRelationMany2ManyUpdateCreateSchemaUserRelationNestedUpdate;
  acl_ids: SchemaRelationOne2ManyUpdateCreateSchemaAccessListRelationNestedUpdate;
  rule_ids: SchemaRelationOne2ManyUpdateCreateSchemaRuleRelationNestedUpdate;
};
export type SchemaModelNestedPartial = {
  id?: number | null;
  name?: string | null;
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
export type SchemaSearchOutputListSchemaUserNestedPartial = {
  data: SchemaUserNestedPartial[];
  total?: number | null;
  fields: GetListField[];
};
export type SchemaAccessListNestedPartial = {
  id?: number | null;
  active?: boolean | null;
  name?: string | null;
  model_id?: SchemaRelationNested | null;
  role_id?: SchemaRelationNested | null;
  perm_create?: boolean | null;
  perm_read?: boolean | null;
  perm_update?: boolean | null;
  perm_delete?: boolean | null;
};
export type SchemaSearchOutputListSchemaAccessListNestedPartial = {
  data: SchemaAccessListNestedPartial[];
  total?: number | null;
  fields: GetListField[];
};
export type SchemaRuleNestedPartial = {
  id?: number | null;
  name?: string | null;
  role_id?: SchemaRelationNested | null;
};
export type SchemaSearchOutputListSchemaRuleNestedPartial = {
  data: SchemaRuleNestedPartial[];
  total?: number | null;
  fields: GetListField[];
};
export type Role = {
  id: number;
  name: string;
  model_id: SchemaModelNestedPartial;
  user_ids: SchemaSearchOutputListSchemaUserNestedPartial;
  acl_ids: SchemaSearchOutputListSchemaAccessListNestedPartial;
  rule_ids: SchemaSearchOutputListSchemaRuleNestedPartial;
};
export type GetFormField = {
  name: string;
  type: string;
  relatedModel?: string | null;
  relatedField?: string | null;
  options?: any[] | null;
};
export type SchemaGetOutputRole = {
  data: Role;
  fields: {
    [key: string]: GetFormField;
  };
};
export type SchemaGetFieldRelationInput = {
  user_ids: (
    | 'id'
    | 'name'
    | 'login'
    | 'email'
    | 'password_hash'
    | 'password_salt'
    | 'image'
    | 'image_ids'
    | 'role_ids'
  )[];
};
export type SchemaGetFieldRelationInput2 = {
  acl_ids: (
    | 'id'
    | 'active'
    | 'name'
    | 'model_id'
    | 'role_id'
    | 'perm_create'
    | 'perm_read'
    | 'perm_update'
    | 'perm_delete'
  )[];
};
export type SchemaGetFieldRelationInput3 = {
  rule_ids: ('id' | 'name' | 'role_id')[];
};
export type SchemaGetInput = {
  fields: (
    | ('id' | 'name' | 'model_id')
    | SchemaGetFieldRelationInput
    | SchemaGetFieldRelationInput2
    | SchemaGetFieldRelationInput3
  )[];
};
export type SchemaRelationOne2ManyUpdateCreateSchemaAttachmentRelationNestedCreate2 =
  {
    created?: SchemaAttachmentRelationNestedCreate[];
    deleted?: number[];
  };
export type SchemaRelationMany2ManyUpdateCreateSchemaRoleRelationNestedCreate2 =
  {
    created?: SchemaRoleRelationNestedCreate[];
    selected?: number[];
    unselected?: number[];
  };
export type SchemaUserRelationNestedUpdate2 = {
  name?: string | null;
  login?: string | null;
  email?: string | null;
  password_hash?: string | null;
  password_salt?: string | null;
  image?: number | 'VirtualId' | null;
  image_ids?: SchemaRelationOne2ManyUpdateCreateSchemaAttachmentRelationNestedCreate2 | null;
  role_ids?: SchemaRelationMany2ManyUpdateCreateSchemaRoleRelationNestedCreate2 | null;
};
export type SchemaRelationMany2ManyUpdateCreateSchemaUserRelationNestedUpdate2 =
  {
    created?: SchemaUserRelationNestedUpdate2[];
    selected?: number[];
    unselected?: number[];
  };
export type RoleUpdate = {
  name?: string | null;
  model_id?: number | 'VirtualId' | null;
  user_ids?: SchemaRelationMany2ManyUpdateCreateSchemaUserRelationNestedUpdate2 | null;
  acl_ids?: SchemaRelationOne2ManyUpdateCreateSchemaAccessListRelationNestedUpdate | null;
  rule_ids?: SchemaRelationOne2ManyUpdateCreateSchemaRuleRelationNestedUpdate | null;
};
export type SchemaUserRelationNestedUpdate3 = {
  name?: string | null;
  login?: string | null;
  email?: string | null;
  password_hash?: string | null;
  password_salt?: string | null;
  image?: number | 'VirtualId' | null;
  image_ids?: SchemaRelationOne2ManyUpdateCreateSchemaAttachmentRelationNestedCreate | null;
  role_ids?: SchemaRelationMany2ManyUpdateCreateSchemaRoleRelationNestedCreate | null;
};
export type SchemaRelationMany2ManyUpdateCreateSchemaUserRelationNestedUpdate3 =
  {
    created?: SchemaUserRelationNestedUpdate3[];
    selected?: number[];
    unselected?: number[];
  };
export type RoleUpdate2 = {
  name?: string | null;
  model_id?: number | 'VirtualId' | null;
  user_ids?: SchemaRelationMany2ManyUpdateCreateSchemaUserRelationNestedUpdate3 | null;
  acl_ids?: SchemaRelationOne2ManyUpdateCreateSchemaAccessListRelationNestedUpdate | null;
  rule_ids?: SchemaRelationOne2ManyUpdateCreateSchemaRuleRelationNestedUpdate | null;
};
export type SchemaGetFieldRelationInput4 = {
  user_ids: (
    | 'id'
    | 'name'
    | 'login'
    | 'email'
    | 'password_hash'
    | 'password_salt'
    | 'image'
    | 'image_ids'
    | 'role_ids'
  )[];
};
export type SchemaGetFieldRelationInput5 = {
  acl_ids: (
    | 'id'
    | 'active'
    | 'name'
    | 'model_id'
    | 'role_id'
    | 'perm_create'
    | 'perm_read'
    | 'perm_update'
    | 'perm_delete'
  )[];
};
export type SchemaGetFieldRelationInput6 = {
  rule_ids: ('id' | 'name' | 'role_id')[];
};
export type SchemaGetInput2 = {
  fields: (
    | ('id' | 'name' | 'model_id')
    | SchemaGetFieldRelationInput4
    | SchemaGetFieldRelationInput5
    | SchemaGetFieldRelationInput6
  )[];
};
export const {
  useRouteRolesSearchPostMutation,
  useRouteRolesSearchMany2ManyGetQuery,
  useLazyRouteRolesSearchMany2ManyGetQuery,
  useRouteRolesPostMutation,
  useRouteRolesDefaultValuesPostMutation,
  useRouteRolesIdPutMutation,
  useRouteRolesIdDeleteMutation,
  useRouteRolesIdPostMutation,
  useRouteRolesBulkDeleteMutation,
} = injectedRtkApi;
