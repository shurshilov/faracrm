export interface FaraRecord {
  id: Identifier | number;
  [key: string]: any;
}
export type VirtualIdType = 'VirtualId';
export const VirtualId = 'VirtualId';

// export interface GetListParams {
//   pagination: PaginationPayload;
//   sort: SortPayload;
//   filter: any;
//   meta?: any;
// }
// export interface GetListResult<RecordType extends RaRecord = any> {}

export type Identifier = string | number;

export type Triplet = [string, string, any];
export type FilterItem = Triplet | 'and' | 'or';
export type FilterExpression = FilterItem[];

export type GetListParams = {
  model: string;
  fields: string[];
  end?: number | null;
  order?: 'desc' | 'asc';
  sort?: string;
  start?: number | null;
  limit?: number;
  filter?: FilterExpression;
  raw?: boolean;
};

export type GetListM2mParams = {
  model: string;
  id: number;
  name: string;
  fields: string[];
  start?: number | null;
  end?: number | null;
  order?: 'desc' | 'asc';
  sort?: string;
  limit?: number;
};
export interface GetListField {
  name: string;
  type: string;
  relation?: string;
  required?: boolean;
}
export interface GetFormField {
  name: string;
  type: string;
  relatedModel?: string;
  relatedField?: string;
  options?: string[];
  required?: boolean;
}
export interface GetListResult<RecordType extends FaraRecord> {
  data: RecordType[];
  total: number;
  fields: GetListField[];
}

export type DeleteListParams = {
  model: string;
  ids: Identifier[];
};
export type DeleteListResult = true;

export type ReadResult<RecordType extends FaraRecord> = {
  data: RecordType;
  fields: Record<string, GetListField>;
};

export type ReadParams = {
  model: string;
  id: Identifier;
  fields?: string[];
};

export type ReadDefaultValuesResult<RecordType extends FaraRecord> = {
  data: RecordType;
  fields: Record<string, GetListField>;
};

export type ReadDefaultValuesParams = {
  model: string;
  fields?: string[];
};

export type EditResult<RecordType extends FaraRecord> = RecordType;
export type EditParams<RecordType extends FaraRecord> = {
  model: string;
  id: Identifier;
  values: RecordType;
  invalidateTags?: string[];
};

export type CreateResult = {
  id: Identifier;
};
export type CreateParams<RecordType> = {
  model: string;
  values: RecordType;
};

export type GetAttachmentParams = {
  id: number;
};
