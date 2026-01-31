import { crudApi as api } from './crudApi';
const injectedRtkApi = api.injectEndpoints({
  endpoints: build => ({
    attachmentContentAttachmentsAttachmentIdGet: build.query<
      AttachmentContentAttachmentsAttachmentIdGetApiResponse,
      AttachmentContentAttachmentsAttachmentIdGetApiArg
    >({
      query: queryArg => ({ url: `/attachments/${queryArg.attachmentId}` }),
    }),
    routeAttachmentsSearchPost: build.mutation<
      RouteAttachmentsSearchPostApiResponse,
      RouteAttachmentsSearchPostApiArg
    >({
      query: queryArg => ({
        url: `/attachments/search`,
        method: 'POST',
        body: queryArg.attachmentSearchInput,
      }),
    }),
    routeAttachmentsSearchMany2ManyGet: build.query<
      RouteAttachmentsSearchMany2ManyGetApiResponse,
      RouteAttachmentsSearchMany2ManyGetApiArg
    >({
      query: queryArg => ({
        url: `/attachments/search_many2many`,
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
    routeAttachmentsPost: build.mutation<
      RouteAttachmentsPostApiResponse,
      RouteAttachmentsPostApiArg
    >({
      query: queryArg => ({
        url: `/attachments`,
        method: 'POST',
        body: queryArg.attachmentCreate,
      }),
    }),
    routeAttachmentsDefaultValuesPost: build.mutation<
      RouteAttachmentsDefaultValuesPostApiResponse,
      RouteAttachmentsDefaultValuesPostApiArg
    >({
      query: queryArg => ({
        url: `/attachments/default_values`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput3,
      }),
    }),
    routeAttachmentsIdPut: build.mutation<
      RouteAttachmentsIdPutApiResponse,
      RouteAttachmentsIdPutApiArg
    >({
      query: queryArg => ({
        url: `/attachments/${queryArg.id}`,
        method: 'PUT',
        body: queryArg.attachmentUpdate,
      }),
    }),
    routeAttachmentsIdDelete: build.mutation<
      RouteAttachmentsIdDeleteApiResponse,
      RouteAttachmentsIdDeleteApiArg
    >({
      query: queryArg => ({
        url: `/attachments/${queryArg.id}`,
        method: 'DELETE',
      }),
    }),
    routeAttachmentsIdPost: build.mutation<
      RouteAttachmentsIdPostApiResponse,
      RouteAttachmentsIdPostApiArg
    >({
      query: queryArg => ({
        url: `/attachments/${queryArg.id}`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput4,
      }),
    }),
    routeAttachmentsBulkDelete: build.mutation<
      RouteAttachmentsBulkDeleteApiResponse,
      RouteAttachmentsBulkDeleteApiArg
    >({
      query: queryArg => ({
        url: `/attachments/bulk`,
        method: 'DELETE',
        body: queryArg.ids,
      }),
    }),
    routeAttachmentsStorageSearchPost: build.mutation<
      RouteAttachmentsStorageSearchPostApiResponse,
      RouteAttachmentsStorageSearchPostApiArg
    >({
      query: queryArg => ({
        url: `/attachments_storage/search`,
        method: 'POST',
        body: queryArg.attachmentStorageSearchInput,
      }),
    }),
    routeAttachmentsStorageSearchMany2ManyGet: build.query<
      RouteAttachmentsStorageSearchMany2ManyGetApiResponse,
      RouteAttachmentsStorageSearchMany2ManyGetApiArg
    >({
      query: queryArg => ({
        url: `/attachments_storage/search_many2many`,
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
    routeAttachmentsStoragePost: build.mutation<
      RouteAttachmentsStoragePostApiResponse,
      RouteAttachmentsStoragePostApiArg
    >({
      query: queryArg => ({
        url: `/attachments_storage`,
        method: 'POST',
        body: queryArg.attachmentStorageCreate,
      }),
    }),
    routeAttachmentsStorageDefaultValuesPost: build.mutation<
      RouteAttachmentsStorageDefaultValuesPostApiResponse,
      RouteAttachmentsStorageDefaultValuesPostApiArg
    >({
      query: queryArg => ({
        url: `/attachments_storage/default_values`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput5,
      }),
    }),
    routeAttachmentsStorageIdPut: build.mutation<
      RouteAttachmentsStorageIdPutApiResponse,
      RouteAttachmentsStorageIdPutApiArg
    >({
      query: queryArg => ({
        url: `/attachments_storage/${queryArg.id}`,
        method: 'PUT',
        body: queryArg.attachmentStorageUpdate,
      }),
    }),
    routeAttachmentsStorageIdDelete: build.mutation<
      RouteAttachmentsStorageIdDeleteApiResponse,
      RouteAttachmentsStorageIdDeleteApiArg
    >({
      query: queryArg => ({
        url: `/attachments_storage/${queryArg.id}`,
        method: 'DELETE',
      }),
    }),
    routeAttachmentsStorageIdPost: build.mutation<
      RouteAttachmentsStorageIdPostApiResponse,
      RouteAttachmentsStorageIdPostApiArg
    >({
      query: queryArg => ({
        url: `/attachments_storage/${queryArg.id}`,
        method: 'POST',
        body: queryArg.backendBaseSystemDotormDotormUtilsSchemaGetInput6,
      }),
    }),
    routeAttachmentsStorageBulkDelete: build.mutation<
      RouteAttachmentsStorageBulkDeleteApiResponse,
      RouteAttachmentsStorageBulkDeleteApiArg
    >({
      query: queryArg => ({
        url: `/attachments_storage/bulk`,
        method: 'DELETE',
        body: queryArg.ids,
      }),
    }),
  }),
  overrideExisting: false,
});
export { injectedRtkApi as crudApi };
export type AttachmentContentAttachmentsAttachmentIdGetApiResponse =
  /** status 200 успешно */ any;
export type AttachmentContentAttachmentsAttachmentIdGetApiArg = {
  attachmentId: number;
};
export type RouteAttachmentsSearchPostApiResponse =
  /** status 200 успешно */ SchemaSearchOutputListAttachmentReadSearchOutput;
export type RouteAttachmentsSearchPostApiArg = {
  attachmentSearchInput: AttachmentSearchInput;
};
export type RouteAttachmentsSearchMany2ManyGetApiResponse =
  /** status 200 успешно */ any;
export type RouteAttachmentsSearchMany2ManyGetApiArg = {
  id: number;
  name: null;
  fields: string[];
  order?: 'desc' | 'asc';
  start?: number | null;
  end?: number | null;
  sort?: string;
  limit?: number;
};
export type RouteAttachmentsPostApiResponse =
  /** status 200 успешно */ SchemaCreateOutput;
export type RouteAttachmentsPostApiArg = {
  attachmentCreate: AttachmentCreate;
};
export type RouteAttachmentsDefaultValuesPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputAttachment;
export type RouteAttachmentsDefaultValuesPostApiArg = {
  backendBaseSystemDotormDotormUtilsSchemaGetInput3: SchemaGetInput;
};
export type RouteAttachmentsIdPutApiResponse =
  /** status 200 успешно */ AttachmentUpdate;
export type RouteAttachmentsIdPutApiArg = {
  id: number;
  attachmentUpdate: AttachmentUpdate;
};
export type RouteAttachmentsIdDeleteApiResponse =
  /** status 200 успешно */ true;
export type RouteAttachmentsIdDeleteApiArg = {
  id: number;
};
export type RouteAttachmentsIdPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputAttachment;
export type RouteAttachmentsIdPostApiArg = {
  id: number;
  backendBaseSystemDotormDotormUtilsSchemaGetInput4: SchemaGetInput2;
};
export type RouteAttachmentsBulkDeleteApiResponse =
  /** status 200 успешно */ true;
export type RouteAttachmentsBulkDeleteApiArg = {
  ids: number[];
};
export type RouteAttachmentsStorageSearchPostApiResponse =
  /** status 200 успешно */ SchemaSearchOutputListAttachmentStorageReadSearchOutput;
export type RouteAttachmentsStorageSearchPostApiArg = {
  attachmentStorageSearchInput: AttachmentStorageSearchInput;
};
export type RouteAttachmentsStorageSearchMany2ManyGetApiResponse =
  /** status 200 успешно */ any;
export type RouteAttachmentsStorageSearchMany2ManyGetApiArg = {
  id: number;
  name: null;
  fields: string[];
  order?: 'desc' | 'asc';
  start?: number | null;
  end?: number | null;
  sort?: string;
  limit?: number;
};
export type RouteAttachmentsStoragePostApiResponse =
  /** status 200 успешно */ SchemaCreateOutput;
export type RouteAttachmentsStoragePostApiArg = {
  attachmentStorageCreate: AttachmentStorageCreate;
};
export type RouteAttachmentsStorageDefaultValuesPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputAttachmentStorage;
export type RouteAttachmentsStorageDefaultValuesPostApiArg = {
  backendBaseSystemDotormDotormUtilsSchemaGetInput5: SchemaGetInput3;
};
export type RouteAttachmentsStorageIdPutApiResponse =
  /** status 200 успешно */ AttachmentStorageUpdate;
export type RouteAttachmentsStorageIdPutApiArg = {
  id: number;
  attachmentStorageUpdate: AttachmentStorageUpdate;
};
export type RouteAttachmentsStorageIdDeleteApiResponse =
  /** status 200 успешно */ true;
export type RouteAttachmentsStorageIdDeleteApiArg = {
  id: number;
};
export type RouteAttachmentsStorageIdPostApiResponse =
  /** status 200 успешно */ SchemaGetOutputAttachmentStorage;
export type RouteAttachmentsStorageIdPostApiArg = {
  id: number;
  backendBaseSystemDotormDotormUtilsSchemaGetInput6: SchemaGetInput4;
};
export type RouteAttachmentsStorageBulkDeleteApiResponse =
  /** status 200 успешно */ true;
export type RouteAttachmentsStorageBulkDeleteApiArg = {
  ids: number[];
};
export type SchemaRelationNested = {
  id: number;
  name: string;
};
export type AttachmentReadSearchOutput = {
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
  is_voice?: boolean | null;
  show_preview?: boolean | null;
  content?: Blob | null;
};
export type GetListField = {
  name: string;
  type: string;
  relation?: string | null;
};
export type SchemaSearchOutputListAttachmentReadSearchOutput = {
  data: AttachmentReadSearchOutput[];
  total?: number | null;
  fields: GetListField[];
};
export type AttachmentSearchInput = {
  fields: (
    | 'id'
    | 'name'
    | 'res_model'
    | 'res_field'
    | 'res_id'
    | 'public'
    | 'folder'
    | 'access_token'
    | 'size'
    | 'checksum'
    | 'mimetype'
    | 'storage_id'
    | 'storage_file_id'
    | 'storage_parent_id'
    | 'storage_parent_name'
    | 'storage_file_url'
    | 'is_voice'
    | 'show_preview'
    | 'content'
  )[];
  end?: number | null;
  order?: 'DESC' | 'ASC' | 'desc' | 'asc';
  sort?:
    | 'id'
    | 'name'
    | 'res_model'
    | 'res_field'
    | 'res_id'
    | 'public'
    | 'folder'
    | 'access_token'
    | 'size'
    | 'checksum'
    | 'mimetype'
    | 'storage_id'
    | 'storage_file_id'
    | 'storage_parent_id'
    | 'storage_parent_name'
    | 'storage_file_url'
    | 'content';
  start?: number | null;
  limit?: number;
  filter?: (
    | ['id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['name', '=' | '>' | '<' | '!=' | '>=' | '<=', string | null]
    | ['res_model', '=' | '>' | '<' | '!=' | '>=' | '<=', string | null]
    | ['res_field', '=' | '>' | '<' | '!=' | '>=' | '<=', string | null]
    | ['res_id', '=' | '>' | '<' | '!=' | '>=' | '<=', number | null]
    | ['public', '=' | '>' | '<' | '!=' | '>=' | '<=', boolean | null]
    | ['folder', '=' | '>' | '<' | '!=' | '>=' | '<=', boolean | null]
    | ['access_token', '=' | '>' | '<' | '!=' | '>=' | '<=', string | null]
    | ['size', '=' | '>' | '<' | '!=' | '>=' | '<=', number | null]
    | ['checksum', '=' | '>' | '<' | '!=' | '>=' | '<=', string | null]
    | ['mimetype', '=' | '>' | '<' | '!=' | '>=' | '<=', string | null]
    | ['storage_id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | ['storage_file_id', '=' | '>' | '<' | '!=' | '>=' | '<=', string | null]
    | ['storage_parent_id', '=' | '>' | '<' | '!=' | '>=' | '<=', string | null]
    | [
        'storage_parent_name',
        '=' | '>' | '<' | '!=' | '>=' | '<=',
        string | null,
      ]
    | ['storage_file_url', '=' | '>' | '<' | '!=' | '>=' | '<=', string | null]
    | ['content', '=' | '>' | '<' | '!=' | '>=' | '<=', Blob | null]
  )[];
  raw?: boolean;
};
export type SchemaCreateOutput = {
  id: number;
};
export type AttachmentCreate = {
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
  storage_id: number | 'VirtualId';
  storage_file_id: string | null;
  storage_parent_id: string | null;
  storage_parent_name: string | null;
  storage_file_url: string | null;
  content: Blob | null;
};
export type SchemaAttachmentStorageNestedPartial = {
  id?: number | null;
  name?: string | null;
  type?: string | null;
};
export type Attachment = {
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
  storage_id: SchemaAttachmentStorageNestedPartial;
  storage_file_id: string | null;
  storage_parent_id: string | null;
  storage_parent_name: string | null;
  storage_file_url: string | null;
  is_voice: boolean | null;
  show_preview: boolean | null;
  content: Blob | null;
};
export type GetFormField = {
  name: string;
  type: string;
  relatedModel?: string | null;
  relatedField?: string | null;
  options?: any[] | null;
};
export type SchemaGetOutputAttachment = {
  data: Attachment;
  fields: {
    [key: string]: GetFormField;
  };
};
export type SchemaGetInput = {
  fields: (
    | 'id'
    | 'name'
    | 'res_model'
    | 'res_field'
    | 'res_id'
    | 'public'
    | 'folder'
    | 'access_token'
    | 'size'
    | 'checksum'
    | 'mimetype'
    | 'storage_id'
    | 'storage_file_id'
    | 'storage_parent_id'
    | 'storage_parent_name'
    | 'storage_file_url'
    | 'content'
  )[];
};
export type AttachmentUpdate = {
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
export type SchemaGetInput2 = {
  fields: (
    | 'id'
    | 'name'
    | 'res_model'
    | 'res_field'
    | 'res_id'
    | 'public'
    | 'folder'
    | 'access_token'
    | 'size'
    | 'checksum'
    | 'mimetype'
    | 'storage_id'
    | 'storage_file_id'
    | 'storage_parent_id'
    | 'storage_parent_name'
    | 'storage_file_url'
    | 'content'
  )[];
};
export type AttachmentStorageReadSearchOutput = {
  id?: number | null;
  name?: string | null;
  type?: string | null;
};
export type SchemaSearchOutputListAttachmentStorageReadSearchOutput = {
  data: AttachmentStorageReadSearchOutput[];
  total?: number | null;
  fields: GetListField[];
};
export type AttachmentStorageSearchInput = {
  fields: ('id' | 'name' | 'type')[];
  end?: number | null;
  order?: 'DESC' | 'ASC' | 'desc' | 'asc';
  sort?: 'id' | 'name' | 'type';
  start?: number | null;
  limit?: number;
  filter?: (
    | ['id', '=' | '>' | '<' | '!=' | '>=' | '<=', number]
    | [
        'name',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
    | [
        'type',
        '=' | 'like' | 'ilike' | '=like' | '=ilike' | 'not ilike' | 'not like',
        string,
      ]
  )[];
  raw?: boolean;
};
export type AttachmentStorageCreate = {
  name: string;
  type?: string;
};
export type AttachmentStorage = {
  id: number;
  name: string;
  type?: string;
};
export type SchemaGetOutputAttachmentStorage = {
  data: AttachmentStorage;
  fields: {
    [key: string]: GetFormField;
  };
};
export type SchemaGetInput3 = {
  fields: ('id' | 'name' | 'type')[];
};
export type AttachmentStorageUpdate = {
  name?: string | null;
  type?: string | null;
};
export type SchemaGetInput4 = {
  fields: ('id' | 'name' | 'type')[];
};
export const {
  useAttachmentContentAttachmentsAttachmentIdGetQuery,
  useLazyAttachmentContentAttachmentsAttachmentIdGetQuery,
  useRouteAttachmentsSearchPostMutation,
  useRouteAttachmentsSearchMany2ManyGetQuery,
  useLazyRouteAttachmentsSearchMany2ManyGetQuery,
  useRouteAttachmentsPostMutation,
  useRouteAttachmentsDefaultValuesPostMutation,
  useRouteAttachmentsIdPutMutation,
  useRouteAttachmentsIdDeleteMutation,
  useRouteAttachmentsIdPostMutation,
  useRouteAttachmentsBulkDeleteMutation,
  useRouteAttachmentsStorageSearchPostMutation,
  useRouteAttachmentsStorageSearchMany2ManyGetQuery,
  useLazyRouteAttachmentsStorageSearchMany2ManyGetQuery,
  useRouteAttachmentsStoragePostMutation,
  useRouteAttachmentsStorageDefaultValuesPostMutation,
  useRouteAttachmentsStorageIdPutMutation,
  useRouteAttachmentsStorageIdDeleteMutation,
  useRouteAttachmentsStorageIdPostMutation,
  useRouteAttachmentsStorageBulkDeleteMutation,
} = injectedRtkApi;
