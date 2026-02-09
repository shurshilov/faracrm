/**
 * attachments.ts — types only (codegen hooks removed, CRUD via generic crudApi.ts)
 */

export type SchemaAttachmentStorage = {
  id: number;
  name?: string | null;
  type?: string | null;
  active?: boolean | null;
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
  storage_id: any;
  storage_file_id: string | null;
  storage_parent_id: string | null;
  storage_parent_name: string | null;
  storage_file_url: string | null;
  is_voice: boolean | null;
  show_preview: boolean | null;
  content: Blob | null;
};
