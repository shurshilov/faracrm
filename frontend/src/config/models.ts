import { MenuGroup, MenuGroups } from './menuGroups';
import { ComponentType } from 'react';

export interface ModelConfig {
  menu?: MenuGroup;
  list?: () => Promise<{ default: ComponentType<any> }>;
  form?: () => Promise<{ default: ComponentType<any> }>;
  kanban?: () => Promise<{ default: ComponentType<any> }>;
  gantt?: () => Promise<{ default: ComponentType<any> }>;
  // Поля только для Generic* компонентов
  fields?: string[];
  // Модули-расширения формы (загружаются при открытии формы)
  extensions?: (() => Promise<any>)[];
}

export const modelsConfig: Record<string, ModelConfig> = {
  // === Stock ===
  products: {
    menu: MenuGroups.stock,
    list: () =>
      import('@/fara_products/List').then(m => ({ default: m.ViewList })),
    form: () =>
      import('@/fara_products/Form').then(m => ({ default: m.ViewForm })),
    kanban: () =>
      import('@/fara_products/Kanban').then(m => ({ default: m.ViewKanban })),
  },
  category: {
    menu: MenuGroups.stock,
    list: () =>
      import('@/fara_products/List').then(m => ({
        default: m.ViewListCategory,
      })),
    form: () =>
      import('@/fara_products/Form').then(m => ({
        default: m.ViewFormCategory,
      })),
    kanban: () =>
      import('@/fara_products/Kanban').then(m => ({
        default: m.ViewKanbanCategory,
      })),
  },
  uom: {
    menu: MenuGroups.stock,
    list: () =>
      import('@/fara_products/List').then(m => ({ default: m.ViewListUom })),
    form: () =>
      import('@/fara_products/Form').then(m => ({ default: m.ViewFormUom })),
    kanban: () =>
      import('@/fara_products/Kanban').then(m => ({
        default: m.ViewKanbanUom,
      })),
  },

  // === Contacts (Партнёры) ===
  partners: {
    menu: MenuGroups.contacts,
    list: () =>
      import('@/fara_partners/List').then(m => ({
        default: m.ViewListPartners,
      })),
    form: () =>
      import('@/fara_partners/Form').then(m => ({
        default: m.ViewFormPartners,
      })),
    kanban: () =>
      import('@/fara_partners/Kanban').then(m => ({
        default: m.ViewKanbanPartners,
      })),
  },
  contact: {
    menu: MenuGroups.contacts,
    list: () =>
      import('@/fara_partners/ContactViews').then(m => ({
        default: m.ViewListContacts,
      })),
    form: () =>
      import('@/fara_partners/ContactViews').then(m => ({
        default: m.ViewFormContacts,
      })),
  },
  contact_type: {
    menu: MenuGroups.contacts,
    list: () =>
      import('@/fara_partners/ContactTypeList').then(m => ({
        default: m.ViewListContactTypes,
      })),
  },

  // === CRM ===
  lead: {
    menu: MenuGroups.crm,
    list: () =>
      import('@/fara_leads/List').then(m => ({ default: m.ViewListLeads })),
    form: () =>
      import('@/fara_leads/Form').then(m => ({ default: m.ViewFormLeads })),
    kanban: () =>
      import('@/fara_leads/Kanban').then(m => ({ default: m.ViewKanbanLeads })),
  },

  // === Communication ===
  chat_connector: {
    menu: MenuGroups.communication,
    list: () =>
      import('@/fara_chat/components/ConnectorList').then(m => ({
        default: m.ConnectorList,
      })),
    form: () =>
      import('@/fara_chat/components/ConnectorForm').then(m => ({
        default: m.ConnectorForm,
      })),
    // Модули расширяющие форму коннектора
    extensions: [
      () => import('@/fara_chat_telegram'),
      () => import('@/fara_chat_email'),
    ],
  },
  chat_external_account: {
    menu: MenuGroups.communication,
    list: () =>
      import('@/fara_chat/components/ExternalAccountViews').then(m => ({
        default: m.ViewListExternalAccount,
      })),
    form: () =>
      import('@/fara_chat/components/ExternalAccountViews').then(m => ({
        default: m.ViewFormExternalAccount,
      })),
  },
  chat_external_chat: {
    menu: MenuGroups.communication,
    list: () =>
      import('@/fara_chat/components/ExternalChatViews').then(m => ({
        default: m.ViewListExternalChat,
      })),
    form: () =>
      import('@/fara_chat/components/ExternalChatViews').then(m => ({
        default: m.ViewFormExternalChat,
      })),
  },
  chat_external_message: {
    menu: MenuGroups.communication,
    list: () =>
      import('@/fara_chat/components/ExternalMessageViews').then(m => ({
        default: m.ViewListExternalMessage,
      })),
    form: () =>
      import('@/fara_chat/components/ExternalMessageViews').then(m => ({
        default: m.ViewFormExternalMessage,
      })),
  },
  lead_stage: {
    menu: MenuGroups.crm,
    list: () =>
      import('@/fara_leads/List').then(m => ({ default: m.ViewListLeadStage })),
    form: () =>
      import('@/fara_leads/Form').then(m => ({ default: m.ViewFormLeadStage })),
    kanban: () =>
      import('@/fara_leads/Kanban').then(m => ({
        default: m.ViewKanbanLeadStage,
      })),
  },
  team_crm: {
    menu: MenuGroups.crm,
    list: () =>
      import('@/fara_leads/List').then(m => ({ default: m.ViewListTeamCrm })),
    form: () =>
      import('@/fara_leads/Form').then(m => ({ default: m.ViewFormTeamCrm })),
    kanban: () =>
      import('@/fara_leads/Kanban').then(m => ({
        default: m.ViewKanbanTeamCrm,
      })),
  },

  // === Sales ===
  sale: {
    menu: MenuGroups.sales,
    list: () =>
      import('@/fara_sales/List').then(m => ({ default: m.ViewListSales })),
    form: () =>
      import('@/fara_sales/Form').then(m => ({ default: m.ViewFormSales })),
    kanban: () =>
      import('@/fara_sales/Kanban').then(m => ({ default: m.ViewKanbanSales })),
  },
  sale_stage: {
    menu: MenuGroups.sales,
    list: () =>
      import('@/fara_sales/List').then(m => ({ default: m.ViewListSaleStage })),
    form: () =>
      import('@/fara_sales/Form').then(m => ({ default: m.ViewFormSaleStage })),
    kanban: () =>
      import('@/fara_sales/Kanban').then(m => ({
        default: m.ViewKanbanSaleStage,
      })),
  },
  tax: {
    menu: MenuGroups.sales,
    list: () =>
      import('@/fara_sales/List').then(m => ({ default: m.ViewListTax })),
    form: () =>
      import('@/fara_sales/Form').then(m => ({ default: m.ViewFormTax })),
    kanban: () =>
      import('@/fara_sales/Kanban').then(m => ({ default: m.ViewKanbanTax })),
  },
  sale_line: {
    list: () =>
      import('@/fara_sales/List').then(m => ({ default: m.ViewListSaleLines })),
    form: () =>
      import('@/fara_sales/Form').then(m => ({ default: m.ViewFormSaleLines })),
  },

  // === Files ===
  attachments: {
    menu: MenuGroups.files,
    list: () =>
      import('@/fara_attachments/List').then(m => ({
        default: m.ViewListAttachments,
      })),
    form: () =>
      import('@/fara_attachments/Form').then(m => ({
        default: m.ViewFormAttachments,
      })),
    kanban: () =>
      import('@/fara_attachments/Kanban').then(m => ({
        default: m.ViewKanbanAttachments,
      })),
  },
  attachments_storage: {
    menu: MenuGroups.files,
    list: () =>
      import('@/fara_attachments/List').then(m => ({
        default: m.ViewListAttachmentsStorage,
      })),
    form: () =>
      import('@/fara_attachments/Form').then(m => ({
        default: m.ViewFormAttachmentsStorage,
      })),
    kanban: () =>
      import('@/fara_attachments/Kanban').then(m => ({
        default: m.ViewKanbanAttachmentsStorage,
      })),
    // Модули расширяющие форму хранилища
    extensions: [() => import('@/fara_attachments_google')],
  },
  attachments_route: {
    menu: MenuGroups.files,
    list: () =>
      import('@/fara_attachments/List').then(m => ({
        default: m.ViewListAttachmentsRoute,
      })),
    form: () =>
      import('@/fara_attachments/Form').then(m => ({
        default: m.ViewFormAttachmentsRoute,
      })),
  },

  // === Settings ===
  company: {
    menu: MenuGroups.settings,
    list: () =>
      import('@/fara_company/List').then(m => ({ default: m.ViewListCompany })),
    form: () =>
      import('@/fara_company/Form').then(m => ({ default: m.ViewFormCompany })),
    kanban: () =>
      import('@/fara_company/Kanban').then(m => ({
        default: m.ViewKanbanCompany,
      })),
  },
  users: {
    menu: MenuGroups.settings,
    list: () => import('@/fara_users/List'),
    form: () => import('@/fara_users/Form'),
    kanban: () => import('@/fara_users/Kanban'),
  },
  roles: {
    menu: MenuGroups.settings,
    list: () =>
      import('@/fara_security/List').then(m => ({ default: m.ViewListRoles })),
    form: () =>
      import('@/fara_security/Form').then(m => ({ default: m.ViewFormRoles })),
    kanban: () =>
      import('@/fara_security/Kanban').then(m => ({
        default: m.ViewKanbanRoles,
      })),
  },
  rules: {
    menu: MenuGroups.settings,
    list: () =>
      import('@/fara_security/List').then(m => ({ default: m.ViewListRules })),
    form: () =>
      import('@/fara_security/Form').then(m => ({ default: m.ViewFormRules })),
    kanban: () =>
      import('@/fara_security/Kanban').then(m => ({
        default: m.ViewKanbanRules,
      })),
  },
  access_list: {
    menu: MenuGroups.settings,
    list: () =>
      import('@/fara_security/List').then(m => ({
        default: m.ViewListAccessList,
      })),
    form: () =>
      import('@/fara_security/Form').then(m => ({
        default: m.ViewFormAccessList,
      })),
    kanban: () =>
      import('@/fara_security/Kanban').then(m => ({
        default: m.ViewKanbanAccessList,
      })),
  },
  models: {
    menu: MenuGroups.settings,
    list: () =>
      import('@/fara_security/List').then(m => ({ default: m.ViewListModels })),
    form: () =>
      import('@/fara_security/Form').then(m => ({ default: m.ViewFormModels })),
    kanban: () =>
      import('@/fara_security/Kanban').then(m => ({
        default: m.ViewKanbanModels,
      })),
  },
  apps: {
    menu: MenuGroups.settings,
    list: () =>
      import('@/fara_security/List').then(m => ({ default: m.ViewListApps })),
    form: () =>
      import('@/fara_security/Form').then(m => ({ default: m.ViewFormApps })),
    kanban: () =>
      import('@/fara_security/Kanban').then(m => ({
        default: m.ViewKanbanApps,
      })),
  },
  sessions: {
    menu: MenuGroups.settings,
    list: () =>
      import('@/fara_security/List').then(m => ({
        default: m.ViewListSessions,
      })),
    form: () =>
      import('@/fara_security/Form').then(m => ({
        default: m.ViewFormSessions,
      })),
    kanban: () =>
      import('@/fara_security/Kanban').then(m => ({
        default: m.ViewKanbanSessions,
      })),
    gantt: () =>
      import('@/fara_security/Gantt').then(m => ({
        default: m.ViewGanttSessions,
      })),
  },
  language: {
    menu: MenuGroups.settings,
    list: () =>
      import('@/fara_languages/List').then(m => ({
        default: m.ViewListLanguage,
      })),
    form: () =>
      import('@/fara_languages/Form').then(m => ({
        default: m.ViewFormLanguage,
      })),
    kanban: () =>
      import('@/fara_languages/Kanban').then(m => ({
        default: m.ViewKanbanLanguage,
      })),
  },
  cron_job: {
    menu: MenuGroups.settings,
    list: () =>
      import('@/fara_cron/List').then(m => ({ default: m.ViewListCronJob })),
    form: () =>
      import('@/fara_cron/Form').then(m => ({ default: m.ViewFormCronJob })),
  },
  saved_filters: {
    menu: MenuGroups.settings,
    list: () =>
      import('@/fara_saved_filters/List').then(m => ({
        default: m.ViewListSavedFilters,
      })),
    form: () =>
      import('@/fara_saved_filters/Form').then(m => ({
        default: m.ViewFormSavedFilters,
      })),
  },
  system_settings: {
    menu: MenuGroups.settings,
    list: () =>
      import('@/fara_system_settings/List').then(m => ({
        default: m.ViewListSystemSettings,
      })),
    form: () =>
      import('@/fara_system_settings/Form').then(m => ({
        default: m.ViewFormSystemSettings,
      })),
  },
};

// Хелпер для получения конфига
export function getModelConfig(model: string): ModelConfig | undefined {
  return modelsConfig[model];
}

// Проверка наличия view
export function hasKanban(model: string): boolean {
  return !!modelsConfig[model]?.kanban;
}

export function hasGantt(model: string): boolean {
  return !!modelsConfig[model]?.gantt;
}
