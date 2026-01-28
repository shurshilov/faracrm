export type SimpleFieldTypes =
  | 'Integer'
  | 'Char'
  | 'Text'
  | 'Boolean'
  | 'Float'
  | 'Datetime'
  | 'Date'
  | 'Time'
  | 'Json'
  | 'File';
export type RelationFieldTypes =
  | 'Many2one'
  | 'Many2many'
  | 'One2many'
  | 'One2one';

export type FieldTypes = SimpleFieldTypes | RelationFieldTypes;

export interface Field {
  type: string;
  name: string;
}

// export type VirtualId = 'VirtualId';
