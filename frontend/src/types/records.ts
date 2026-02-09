/**
 * records.ts — Полная типизация всех записей (records) FARA CRM.
 *
 * Заменяет `[key: string]: any` в FaraRecord конкретными типами для каждой модели.
 * Базовый FaraRecord остаётся как fallback для generic-компонентов.
 *
 * Паттерн: Many2one поля возвращают RelationRecord | null,
 *          One2many/Many2many — RelationRecord[].
 */

import type { Identifier } from '@/services/api/crudTypes';

// ============================================================
// Базовые вспомогательные типы
// ============================================================

/** Минимальная вложенная запись для связей Many2one / One2many / Many2many */
export interface RelationRecord {
  id: number;
  name?: string;
  [key: string]: any; // сервер может прислать доп. поля
}

/** Базовая запись — id + произвольные поля */
export interface BaseRecord {
  id: Identifier;
}

// ============================================================
// Модели: CRM
// ============================================================

export interface LeadRecord extends BaseRecord {
  name: string;
  active: boolean;
  stage_id: RelationRecord | null;
  user_id: RelationRecord | null;
  parent_id: RelationRecord | null;
  company_id: RelationRecord | null;
  notes: string | null;
  type: 'lead' | 'opportunity';
  website: string | null;
  email: string | null;
  phone: string | null;
  mobile: string | null;
}

export interface LeadStageRecord extends BaseRecord {
  name: string;
  sequence: number;
  active: boolean;
  fold: boolean;
  color: string;
}

export interface TeamCrmRecord extends BaseRecord {
  name: string;
}

// ============================================================
// Модели: Sales
// ============================================================

export interface SaleRecord extends BaseRecord {
  name: string;
  active: boolean;
  stage_id: RelationRecord | null;
  user_id: RelationRecord | null;
  partner_id: RelationRecord | null;
  company_id: RelationRecord | null;
  order_line_ids: RelationRecord[];
  notes: string | null;
  date_order: string | null;
  origin: string | null;
}

export interface SaleLineRecord extends BaseRecord {
  sale_id: RelationRecord | null;
  sequence: number;
  notes: string | null;
  product_id: RelationRecord | null;
  product_uom_qty: number;
  product_uom_id: RelationRecord | null;
  tax_id: RelationRecord | null;
  price_unit: number;
  discount: number;
  price_subtotal: number;
  price_tax: number;
  price_total: number;
}

export interface SaleStageRecord extends BaseRecord {
  name: string;
  sequence: number;
  active: boolean;
  fold: boolean;
  color: string;
}

export interface TaxRecord extends BaseRecord {
  name: string;
  amount: number;
}

// ============================================================
// Модели: Partners / Contacts
// ============================================================

export interface PartnerRecord extends BaseRecord {
  name: string;
  active: boolean;
  image: RelationRecord | null;
  parent_id: RelationRecord | null;
  child_ids: RelationRecord[];
  user_id: RelationRecord | null;
  company_id: RelationRecord | null;
  tz: string | null;
  lang: string | null;
  vat: string | null;
  notes: string | null;
  website: string | null;
  contact_ids: RelationRecord[];
}

export interface ContactRecord extends BaseRecord {
  name: string;
  partner_id: RelationRecord | null;
  user_id: RelationRecord | null;
  contact_type_id: RelationRecord | null;
  external_account_ids: RelationRecord[];
  is_primary: boolean;
  active: boolean;
  create_date: string | null;
  write_date: string | null;
}

export interface ContactTypeRecord extends BaseRecord {
  name: string;
  label: string;
  icon: string | null;
  color: string;
  placeholder: string | null;
  pattern: string | null;
  connector_ids: RelationRecord[];
  sequence: number;
  active: boolean;
}

// ============================================================
// Модели: Products
// ============================================================

export interface ProductRecord extends BaseRecord {
  name: string;
  sequence: number;
  description: string | null;
  type: 'consu' | 'service' | 'combo';
  uom_id: RelationRecord | null;
  company_id: RelationRecord | null;
  category_id: RelationRecord | null;
  default_code: string | null;
  code: string | null;
  barcode: string | null;
  extra_price: number | null;
  list_price: number;
  standard_price: number | null;
  volume: number | null;
  weight: number | null;
  image: RelationRecord | null;
  active: boolean;
}

export interface CategoryRecord extends BaseRecord {
  name: string;
}

export interface UomRecord extends BaseRecord {
  name: string;
}

// ============================================================
// Модели: Company
// ============================================================

export interface CompanyRecord extends BaseRecord {
  name: string;
  active: boolean;
  sequence: number;
  parent_id: RelationRecord | null;
  child_ids: RelationRecord[];
}

// ============================================================
// Модели: Tasks / Projects
// ============================================================

export interface TaskRecord extends BaseRecord {
  name: string;
  active: boolean;
  sequence: number;
  description: string | null;
  project_id: RelationRecord | null;
  stage_id: RelationRecord | null;
  parent_id: RelationRecord | null;
  child_ids: RelationRecord[];
  user_id: RelationRecord | null;
  priority: 'low' | 'medium' | 'high' | 'urgent';
  tag_ids: RelationRecord[];
  date_start: string | null;
  date_end: string | null;
  date_deadline: string | null;
  planned_hours: number;
  effective_hours: number;
  progress: number;
  color: string;
}

export interface ProjectRecord extends BaseRecord {
  name: string;
  active: boolean;
  description: string | null;
  color: string;
  status: 'active' | 'on_hold' | 'done' | 'cancelled';
  manager_id: RelationRecord | null;
  date_start: string | null;
  date_end: string | null;
  task_ids: RelationRecord[];
}

export interface TaskStageRecord extends BaseRecord {
  name: string;
  sequence: number;
  active: boolean;
  fold: boolean;
  color: string;
  is_closed: boolean;
}

export interface TaskTagRecord extends BaseRecord {
  name: string;
  color: string;
  active: boolean;
}

// ============================================================
// Модели: Activity
// ============================================================

export interface ActivityRecord extends BaseRecord {
  res_model: string;
  res_id: number;
  activity_type_id: RelationRecord | null;
  summary: string | null;
  note: string | null;
  date_deadline: string;
  user_id: RelationRecord | null;
  create_user_id: RelationRecord | null;
  state: 'planned' | 'today' | 'overdue' | 'done' | 'cancelled';
  done: boolean;
  done_datetime: string | null;
  active: boolean;
  create_date: string | null;
  notification_sent: boolean;
}

export interface ActivityTypeRecord extends BaseRecord {
  name: string;
  icon: string | null;
  color: string;
  default_days: number;
  sequence: number;
  active: boolean;
}

// ============================================================
// Модели: Users
// ============================================================

export interface UserRecord extends BaseRecord {
  name: string;
  login: string;
  email?: string | null;
  is_admin: boolean;
  image: RelationRecord | null;
  role_ids: RelationRecord[];
  lang_id: RelationRecord | null;
  lang_ids: RelationRecord[];
  contact_ids: RelationRecord[];
  home_page: string;
  layout_theme: 'classic' | 'modern';
}

// ============================================================
// Модели: Security
// ============================================================

export interface RoleRecord extends BaseRecord {
  code: string;
  name: string;
  app_id: RelationRecord | null;
  based_role_ids: RelationRecord[];
  model_id: RelationRecord | null;
  user_ids: RelationRecord[];
  acl_ids: RelationRecord[];
  rule_ids: RelationRecord[];
}

export interface RuleRecord extends BaseRecord {
  name: string;
  active: boolean;
  model_id: RelationRecord | null;
  role_id: RelationRecord | null;
  domain: unknown;
  perm_create: boolean;
  perm_read: boolean;
  perm_update: boolean;
  perm_delete: boolean;
}

export interface AccessListRecord extends BaseRecord {
  name: string;
  active: boolean;
  model_id: RelationRecord | null;
  role_id: RelationRecord | null;
  perm_create: boolean;
  perm_read: boolean;
  perm_update: boolean;
  perm_delete: boolean;
}

export interface ModelRecord extends BaseRecord {
  name: string;
}

export interface AppRecord extends BaseRecord {
  code: string;
  name: string;
  active: boolean;
  sequence: number;
}

export interface SessionRecord extends BaseRecord {
  active: boolean;
  user_id: RelationRecord | null;
  token: string;
  ttl: number;
  expired_datetime: string | null;
  create_datetime: string | null;
  create_user_id: RelationRecord | null;
  update_datetime: string | null;
  update_user_id: RelationRecord | null;
}

// ============================================================
// Модели: Chat
// ============================================================

export interface ChatConnectorRecord extends BaseRecord {
  name: string;
  active: boolean;
  type: string;
}

export interface ChatExternalAccountRecord extends BaseRecord {
  external_id: string;
  connector_id: RelationRecord | null;
  contact_id: RelationRecord | null;
}

export interface ChatExternalChatRecord extends BaseRecord {
  external_id: string;
  connector_id: RelationRecord | null;
  chat_id: RelationRecord | null;
}

export interface ChatExternalMessageRecord extends BaseRecord {
  external_id: string;
  connector_id: RelationRecord | null;
  message_id: RelationRecord | null;
}

// ============================================================
// Модели: Attachments
// ============================================================

export interface AttachmentRecord extends BaseRecord {
  name: string;
  active: boolean;
  res_model: string | null;
  res_id: number | null;
  storage_id: RelationRecord | null;
}

export interface AttachmentStorageRecord extends BaseRecord {
  name: string;
  type: string;
  active: boolean;
}

export interface AttachmentRouteRecord extends BaseRecord {
  name: string;
  active: boolean;
  storage_id: RelationRecord | null;
}

// ============================================================
// Модели: Contract
// ============================================================

export interface ContractRecord extends BaseRecord {
  name: string | null;
  active: boolean;
  partner_id: RelationRecord | null;
  company_id: RelationRecord | null;
}

// ============================================================
// Модели: Settings / System
// ============================================================

export interface LanguageRecord extends BaseRecord {
  code: string;
  name: string;
  flag: string;
  active: boolean;
}

export interface CronJobRecord extends BaseRecord {
  name: string;
  active: boolean;
}

export interface SavedFilterRecord extends BaseRecord {
  name: string;
  model_name: string;
  filter_data: string;
  user_id: RelationRecord | null;
  is_global: boolean;
  is_default: boolean;
  created_at: string | null;
  last_used_at: string | null;
  use_count: number;
}

export interface SystemSettingRecord extends BaseRecord {
  key: string;
  value: unknown;
}

export interface ReportTemplateRecord extends BaseRecord {
  name: string;
  active: boolean;
  model_name: string;
}

// ============================================================
// Маппинг model name → Record type
// ============================================================

/**
 * Маппинг строковых имён моделей на типы записей.
 * Используется для типизации generic-компонентов (List, Form, Kanban).
 */
export interface ModelRecordMap {
  // CRM
  lead: LeadRecord;
  lead_stage: LeadStageRecord;
  team_crm: TeamCrmRecord;
  // Sales
  sale: SaleRecord;
  sale_line: SaleLineRecord;
  sale_stage: SaleStageRecord;
  tax: TaxRecord;
  // Partners
  partners: PartnerRecord;
  contact: ContactRecord;
  contact_type: ContactTypeRecord;
  // Products
  products: ProductRecord;
  category: CategoryRecord;
  uom: UomRecord;
  // Company
  company: CompanyRecord;
  // Tasks
  task: TaskRecord;
  project: ProjectRecord;
  task_stage: TaskStageRecord;
  task_tag: TaskTagRecord;
  // Activity
  activity: ActivityRecord;
  activity_type: ActivityTypeRecord;
  // Users
  users: UserRecord;
  // Security
  roles: RoleRecord;
  rules: RuleRecord;
  access_list: AccessListRecord;
  models: ModelRecord;
  apps: AppRecord;
  sessions: SessionRecord;
  // Chat
  chat_connector: ChatConnectorRecord;
  chat_external_account: ChatExternalAccountRecord;
  chat_external_chat: ChatExternalChatRecord;
  chat_external_message: ChatExternalMessageRecord;
  // Attachments
  attachments: AttachmentRecord;
  attachments_storage: AttachmentStorageRecord;
  attachments_route: AttachmentRouteRecord;
  // Contract
  contract: ContractRecord;
  // Settings
  language: LanguageRecord;
  cron_job: CronJobRecord;
  saved_filters: SavedFilterRecord;
  system_settings: SystemSettingRecord;
  report_template: ReportTemplateRecord;
}

/** Все известные имена моделей */
export type ModelName = keyof ModelRecordMap;

/**
 * Хелпер: получить тип записи по имени модели.
 * Для неизвестных моделей возвращает BaseRecord.
 *
 * @example
 *   type R = RecordOf<'lead'>; // LeadRecord
 *   type R = RecordOf<'unknown_model'>; // BaseRecord
 */
export type RecordOf<M extends string> = M extends ModelName
  ? ModelRecordMap[M]
  : BaseRecord;
