import { crudApi as api } from './crudApi';
const injectedRtkApi = api.injectEndpoints({
  endpoints: build => ({
    routeUsersSearchPost: build.mutation<
      RouteUsersSearchPostApiResponse,
      RouteUsersSearchPostApiArg
    >({
      query: queryArg => ({
        url: `/users/search`,
        method: 'POST',
        body: queryArg.userSearchInput,
      }),
    }),
    routeUsersSearchMany2ManyGet: build.query<
      RouteUsersSearchMany2ManyGetApiResponse,
      RouteUsersSearchMany2ManyGetApiArg
    >({
      query: queryArg => ({
        url: `/users/search_many2many`,
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
    routeUsersPost: build.mutation<
      RouteUsersPostApiResponse,
      RouteUsersPostApiArg
    >({
      query: queryArg => ({
        url: `/users`,
        method: 'POST',
        body: queryArg.userCreate,
      }),
    }),
    routeUsersDefaultValuesPost: build.mutation<
      RouteUsersDefaultValuesPostApiResponse,
      RouteUsersDefaultValuesPostApiArg
    >({
      query: queryArg => ({
        url: `/users/default_values`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput35,
      }),
    }),
    routeUsersIdPut: build.mutation<
      RouteUsersIdPutApiResponse,
      RouteUsersIdPutApiArg
    >({
      query: queryArg => ({
        url: `/users/${queryArg.id}`,
        method: 'PUT',
        body: queryArg.userUpdateInput,
      }),
    }),
    routeUsersIdDelete: build.mutation<
      RouteUsersIdDeleteApiResponse,
      RouteUsersIdDeleteApiArg
    >({
      query: queryArg => ({ url: `/users/${queryArg.id}`, method: 'DELETE' }),
    }),
    routeUsersIdPost: build.mutation<
      RouteUsersIdPostApiResponse,
      RouteUsersIdPostApiArg
    >({
      query: queryArg => ({
        url: `/users/${queryArg.id}`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput36,
      }),
    }),
    routeUsersBulkDelete: build.mutation<
      RouteUsersBulkDeleteApiResponse,
      RouteUsersBulkDeleteApiArg
    >({
      query: queryArg => ({
        url: `/users/bulk`,
        method: 'DELETE',
        body: queryArg.ids,
      }),
    }),
    // Change password endpoint
    changePassword: build.mutation<void, ChangePasswordArgs>({
      query: ({ userId, password }) => ({
        url: `/users/password_change`,
        method: 'POST',
        body: {
          user_id: userId,
          password: password,
        },
      }),
    }),
    // Copy user endpoint
    copyUser: build.mutation<CopyUserResponse, CopyUserArgs>({
      query: args => ({
        url: `/users/copy`,
        method: 'POST',
        body: {
          source_user_id: args.source_user_id,
          name: args.name,
          login: args.login,
          copy_password: args.copy_password,
          copy_roles: args.copy_roles,
          copy_files: args.copy_files,
          copy_languages: args.copy_languages,
          copy_is_admin: args.copy_is_admin,
          copy_contacts: args.copy_contacts,
        },
      }),
    }),
  }),
  overrideExisting: false,
});

// Change password types
export type ChangePasswordArgs = {
  userId: number;
  password: string;
};

// Copy user types
export type CopyUserArgs = {
  source_user_id: number;
  name: string;
  login: string;
  copy_password: boolean;
  copy_roles: boolean;
  copy_files: boolean;
  copy_languages: boolean;
  copy_is_admin: boolean;
  copy_contacts: boolean;
};

export type CopyUserResponse = {
  id: number;
  name: string;
  login: string;
};

export { injectedRtkApi as crudApi };
export type RouteUsersSearchPostApiResponse =
  /** status 200 успешно */ SchemaSearchOutputListUserReadSearchOutput;
export type RouteUsersSearchPostApiArg = {
  userSearchInput: UserSearchInput;
};
export type RouteUsersSearchMany2ManyGetApiResponse =
  /** status 200 успешно */ any;
export type RouteUsersSearchMany2ManyGetApiArg = {
  id: number;
  name: 'role_ids';
  fields: string[];
  order?: 'desc' | 'asc';
  start?: number | null;
  end?: number | null;
  sort?: string;
  limit?: number;
};
export type RouteUsersPostApiResponse =
  /** status 200 успешно */ SchemaCreateOutput;
export type RouteUsersPostApiArg = {
  userCreate: UserCreate;
};
export type RouteUsersDefaultValuesPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputUser;
export type RouteUsersDefaultValuesPostApiArg = {
  backendBaseSystemDotormDotormUtilsSchemaGetInput35: SchemaGetInput;
};
export type RouteUsersIdPutApiResponse = /** status 200 успешно */ UserUpdate;
export type RouteUsersIdPutApiArg = {
  id: number;
  userUpdateInput: UserUpdate2;
};
export type RouteUsersIdDeleteApiResponse = /** status 200 успешно */ true;
export type RouteUsersIdDeleteApiArg = {
  id: number;
};
export type RouteUsersIdPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputUser;
export type RouteUsersIdPostApiArg = {
  id: number;
  backendBaseSystemDotormDotormUtilsSchemaGetInput36: SchemaGetInput2;
};
export type RouteUsersBulkDeleteApiResponse = /** status 200 успешно */ true;
export type RouteUsersBulkDeleteApiArg = {
  ids: number[];
};
export type SchemaRelationNested = {
  id: number;
  name: string;
};
export type UserReadSearchOutput = {
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
export type GetListField = {
  name: string;
  type: string;
  relation?: string | null;
};
export type SchemaSearchOutputListUserReadSearchOutput = {
  data: UserReadSearchOutput[];
  total?: number | null;
  fields: GetListField[];
};
export type UserSearchInput = {
  fields: (
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
  end?: number | null;
  order?: 'DESC' | 'ASC' | 'desc' | 'asc';
  sort?:
    | 'id'
    | 'name'
    | 'login'
    | 'email'
    | 'password_hash'
    | 'password_salt'
    | 'image'
    | 'image_ids'
    | 'role_ids';
  start?: number | null;
  limit?: number;
  filter?: (
    | ['id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | [
        'name',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | ['login', '=' | '>' | '<' | '!=' | '>=' | '<=', string | null]
    | [
        'email',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | ['password_hash', '=' | '>' | '<' | '!=' | '>=' | '<=', string | null]
    | ['password_salt', '=' | '>' | '<' | '!=' | '>=' | '<=', string | null]
    | ['image', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['image_ids', 'in' | 'not in', number[]]
    | ['role_ids', 'in' | 'not in', number[]]
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
export type SchemaAttachmentRelationNestedUpdate = {
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
  storage_id?: number | 'VirtualId' | null;
  storage_file_id?: string | null;
  storage_parent_id?: string | null;
  storage_parent_name?: string | null;
  storage_file_url?: string | null;
  content?: Blob | null;
};
export type SchemaRelationOne2ManyUpdateCreateSchemaAttachmentRelationNestedUpdate =
  {
    created?: SchemaAttachmentRelationNestedUpdate[];
    deleted?: number[];
  };
export type SchemaUserRelationNestedCreate = {
  name?: string | null;
  login?: string | null;
  email?: string | null;
  password_hash?: string | null;
  password_salt?: string | null;
  image?: SchemaAttachment | null;
};
export type SchemaRelationMany2ManyUpdateCreateSchemaUserRelationNestedCreate =
  {
    created?: SchemaUserRelationNestedCreate[];
    selected?: number[];
    unselected?: number[];
  };
export type SchemaModel = {
  id: number;
  name: string;
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
export type SchemaAccessListRelationNestedCreate = {
  active?: boolean | null;
  name?: string | null;
  model_id?: SchemaModel | null;
  role_id?: SchemaRole | null;
  perm_create?: boolean | null;
  perm_read?: boolean | null;
  perm_update?: boolean | null;
  perm_delete?: boolean | null;
};
export type SchemaRelationOne2ManyUpdateCreateSchemaAccessListRelationNestedCreate =
  {
    created?: SchemaAccessListRelationNestedCreate[];
    deleted?: number[];
  };
export type SchemaRuleRelationNestedCreate = {
  name?: string | null;
  role_id?: SchemaRole | null;
};
export type SchemaRelationOne2ManyUpdateCreateSchemaRuleRelationNestedCreate = {
  created?: SchemaRuleRelationNestedCreate[];
  deleted?: number[];
};
export type SchemaRoleRelationNestedUpdate = {
  name?: string | null;
  model_id?: number | 'VirtualId' | null;
  user_ids?: SchemaRelationMany2ManyUpdateCreateSchemaUserRelationNestedCreate | null;
  acl_ids?: SchemaRelationOne2ManyUpdateCreateSchemaAccessListRelationNestedCreate | null;
  rule_ids?: SchemaRelationOne2ManyUpdateCreateSchemaRuleRelationNestedCreate | null;
};
export type SchemaRelationMany2ManyUpdateCreateSchemaRoleRelationNestedUpdate =
  {
    created?: SchemaRoleRelationNestedUpdate[];
    selected?: number[];
    unselected?: number[];
  };
export type UserCreate = {
  name: string;
  login: string | null;
  email: string;
  password_hash: string | null;
  password_salt: string | null;
  image: SchemaAttachment | null;
  image_ids: SchemaRelationOne2ManyUpdateCreateSchemaAttachmentRelationNestedUpdate;
  role_ids: SchemaRelationMany2ManyUpdateCreateSchemaRoleRelationNestedUpdate;
};
export type SchemaAttachmentNestedPartial = {
  id?: number | null;
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
  storage_id?: SchemaRelationNested | null;
  storage_file_id?: string | null;
  storage_parent_id?: string | null;
  storage_parent_name?: string | null;
  storage_file_url?: string | null;
  content?: Blob | null;
};
export type SchemaSearchOutputListSchemaAttachmentNestedPartial = {
  data: SchemaAttachmentNestedPartial[];
  total?: number | null;
  fields: GetListField[];
};
export type SchemaRoleNestedPartial = {
  id?: number | null;
  name?: string | null;
  model_id?: SchemaRelationNested | null;
  user_ids?: SchemaRelationNested[] | null;
  acl_ids?: SchemaRelationNested[] | null;
  rule_ids?: SchemaRelationNested[] | null;
};
export type SchemaSearchOutputListSchemaRoleNestedPartial = {
  data: SchemaRoleNestedPartial[];
  total?: number | null;
  fields: GetListField[];
};
export type User = {
  id: number;
  name: string;
  login: string | null;
  email: string;
  password_hash: string | null;
  password_salt: string | null;
  image: SchemaAttachmentNestedPartial;
  image_ids: SchemaSearchOutputListSchemaAttachmentNestedPartial;
  role_ids: SchemaSearchOutputListSchemaRoleNestedPartial;
};
export type GetFormField = {
  name: string;
  type: string;
  relatedModel?: string | null;
  relatedField?: string | null;
  options?: any[] | null;
};
export type SchemaGetOutputUser = {
  data: User;
  fields: {
    [key: string]: GetFormField;
  };
};
export type SchemaGetFieldRelationInput = {
  role_ids: (
    | 'id'
    | 'name'
    | 'model_id'
    | 'user_ids'
    | 'acl_ids'
    | 'rule_ids'
  )[];
};
export type SchemaGetInput = {
  fields: (
    | (
        | 'id'
        | 'name'
        | 'login'
        | 'email'
        | 'password_hash'
        | 'password_salt'
        | 'image'
        | 'image_ids'
      )
    | SchemaGetFieldRelationInput
  )[];
};
export type SchemaUserRelationNestedCreate2 = {
  name?: string | null;
  login?: string | null;
  email?: string | null;
  password_hash?: string | null;
  password_salt?: string | null;
  image?: SchemaAttachment | null;
};
export type SchemaRelationMany2ManyUpdateCreateSchemaUserRelationNestedCreate2 =
  {
    created?: SchemaUserRelationNestedCreate2[];
    selected?: number[];
    unselected?: number[];
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
export type SchemaAccessListRelationNestedCreate2 = {
  active?: boolean | null;
  name?: string | null;
  model_id?: SchemaModel | null;
  role_id?: SchemaRole2 | null;
  perm_create?: boolean | null;
  perm_read?: boolean | null;
  perm_update?: boolean | null;
  perm_delete?: boolean | null;
};
export type SchemaRelationOne2ManyUpdateCreateSchemaAccessListRelationNestedCreate2 =
  {
    created?: SchemaAccessListRelationNestedCreate2[];
    deleted?: number[];
  };
export type SchemaRuleRelationNestedCreate2 = {
  name?: string | null;
  role_id?: SchemaRole2 | null;
};
export type SchemaRelationOne2ManyUpdateCreateSchemaRuleRelationNestedCreate2 =
  {
    created?: SchemaRuleRelationNestedCreate2[];
    deleted?: number[];
  };
export type SchemaRoleRelationNestedUpdate2 = {
  name?: string | null;
  model_id?: number | 'VirtualId' | null;
  user_ids?: SchemaRelationMany2ManyUpdateCreateSchemaUserRelationNestedCreate2 | null;
  acl_ids?: SchemaRelationOne2ManyUpdateCreateSchemaAccessListRelationNestedCreate2 | null;
  rule_ids?: SchemaRelationOne2ManyUpdateCreateSchemaRuleRelationNestedCreate2 | null;
};
export type SchemaRelationMany2ManyUpdateCreateSchemaRoleRelationNestedUpdate2 =
  {
    created?: SchemaRoleRelationNestedUpdate2[];
    selected?: number[];
    unselected?: number[];
  };
export type UserUpdate = {
  name?: string | null;
  login?: string | null;
  email?: string | null;
  password_hash?: string | null;
  password_salt?: string | null;
  image?: SchemaAttachment | null;
  image_ids?: SchemaRelationOne2ManyUpdateCreateSchemaAttachmentRelationNestedUpdate | null;
  role_ids?: SchemaRelationMany2ManyUpdateCreateSchemaRoleRelationNestedUpdate2 | null;
};
export type SchemaRoleRelationNestedUpdate3 = {
  name?: string | null;
  model_id?: number | 'VirtualId' | null;
  user_ids?: SchemaRelationMany2ManyUpdateCreateSchemaUserRelationNestedCreate | null;
  acl_ids?: SchemaRelationOne2ManyUpdateCreateSchemaAccessListRelationNestedCreate | null;
  rule_ids?: SchemaRelationOne2ManyUpdateCreateSchemaRuleRelationNestedCreate | null;
};
export type SchemaRelationMany2ManyUpdateCreateSchemaRoleRelationNestedUpdate3 =
  {
    created?: SchemaRoleRelationNestedUpdate3[];
    selected?: number[];
    unselected?: number[];
  };
export type UserUpdate2 = {
  name?: string | null;
  login?: string | null;
  email?: string | null;
  password_hash?: string | null;
  password_salt?: string | null;
  image?: SchemaAttachment | null;
  image_ids?: SchemaRelationOne2ManyUpdateCreateSchemaAttachmentRelationNestedUpdate | null;
  role_ids?: SchemaRelationMany2ManyUpdateCreateSchemaRoleRelationNestedUpdate3 | null;
};
export type SchemaGetFieldRelationInput2 = {
  role_ids: (
    | 'id'
    | 'name'
    | 'model_id'
    | 'user_ids'
    | 'acl_ids'
    | 'rule_ids'
  )[];
};
export type SchemaGetInput2 = {
  fields: (
    | (
        | 'id'
        | 'name'
        | 'login'
        | 'email'
        | 'password_hash'
        | 'password_salt'
        | 'image'
        | 'image_ids'
      )
    | SchemaGetFieldRelationInput2
  )[];
};
export const {
  useRouteUsersSearchPostMutation,
  useRouteUsersSearchMany2ManyGetQuery,
  useLazyRouteUsersSearchMany2ManyGetQuery,
  useRouteUsersPostMutation,
  useRouteUsersDefaultValuesPostMutation,
  useRouteUsersIdPutMutation,
  useRouteUsersIdDeleteMutation,
  useRouteUsersIdPostMutation,
  useRouteUsersBulkDeleteMutation,
  useChangePasswordMutation,
  useCopyUserMutation,
} = injectedRtkApi;
