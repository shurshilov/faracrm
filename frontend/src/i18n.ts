import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import dayjs from 'dayjs';
import 'dayjs/locale/ru';
import 'dayjs/locale/en';

// ============ Глобальные переводы ============
import enCommon from './locales/en/common.json';
import ruCommon from './locales/ru/common.json';

// ============ Модульные переводы ============
// fara_users
import enUsers from './fara_users/locales/en.json';
import ruUsers from './fara_users/locales/ru.json';

// fara_products
import enProducts from './fara_products/locales/en.json';
import ruProducts from './fara_products/locales/ru.json';

// fara_security
import enSecurity from './fara_security/locales/en.json';
import ruSecurity from './fara_security/locales/ru.json';

// fara_attachments
import enAttachments from './fara_attachments/locales/en.json';
import ruAttachments from './fara_attachments/locales/ru.json';

// fara_languages
import enLanguages from './fara_languages/locales/en.json';
import ruLanguages from './fara_languages/locales/ru.json';

// fara_partners
import enPartners from './fara_partners/locales/en.json';
import ruPartners from './fara_partners/locales/ru.json';

// fara_sales
import enSales from './fara_sales/locales/en.json';
import ruSales from './fara_sales/locales/ru.json';

// fara_leads
import enLeads from './fara_leads/locales/en.json';
import ruLeads from './fara_leads/locales/ru.json';

// fara_company
import enCompany from './fara_company/locales/en.json';
import ruCompany from './fara_company/locales/ru.json';

// fara_chat
import enChat from './fara_chat/locales/en.json';
import ruChat from './fara_chat/locales/ru.json';

// fara_cron
import enCron from './fara_cron/locales/en.json';
import ruCron from './fara_cron/locales/ru.json';

// fara_system_settings
import enSystemSettings from './fara_system_settings/locales/en.json';
import ruSystemSettings from './fara_system_settings/locales/ru.json';

// fara_tasks
import enTasks from './fara_tasks/locales/en.json';
import ruTasks from './fara_tasks/locales/ru.json';

// fara_activity
import enActivity from './fara_activity/locales/en.json';
import ruActivity from './fara_activity/locales/ru.json';

// fara_saved_filters
import enSavedFilters from './fara_saved_filters/locales/en.json';
import ruSavedFilters from './fara_saved_filters/locales/ru.json';

// fara_report_docx
import enReports from './fara_report_docx/locales/en.json';
import ruReports from './fara_report_docx/locales/ru.json';

// fara_workspace
import enWorkspace from './fara_workspace/locales/en.json';
import ruWorkspace from './fara_workspace/locales/ru.json';

// fara_apps — установка/удаление приложений
import enApps from './fara_apps/locales/en.json';
import ruApps from './fara_apps/locales/ru.json';

// fara_registration
import enRegistration from './fara_registration/locales/en.json';
import ruRegistration from './fara_registration/locales/ru.json';

// fara_marketplace
import enMarketplace from './fara_marketplace/locales/en.json';
import ruMarketplace from './fara_marketplace/locales/ru.json';

// components/Docs — пользовательская документация (справка)
import enDocs from './components/Docs/locales/en.json';
import ruDocs from './components/Docs/locales/ru.json';


// ============ Склейка переводов ============
const resources = {
  en: {
    common: enCommon,
    // Объединяем все модульные переводы
    users: enUsers,
    products: enProducts,
    security: enSecurity,
    attachments: enAttachments,
    languages: enLanguages,
    partners: enPartners,
    sales: enSales,
    leads: enLeads,
    company: enCompany,
    chat: enChat,
    cron: enCron,
    system_settings: enSystemSettings,
    activity: enActivity,
    tasks: enTasks,
    saved_filters: enSavedFilters,
    reports: enReports,
    workspace: enWorkspace,
    apps: enApps,
    registration: enRegistration,
    marketplace: enMarketplace,
    docs: enDocs,
  },
  ru: {
    common: ruCommon,
    users: ruUsers,
    products: ruProducts,
    security: ruSecurity,
    attachments: ruAttachments,
    languages: ruLanguages,
    partners: ruPartners,
    sales: ruSales,
    leads: ruLeads,
    company: ruCompany,
    chat: ruChat,
    cron: ruCron,
    system_settings: ruSystemSettings,
    activity: ruActivity,
    tasks: ruTasks,
    saved_filters: ruSavedFilters,
    reports: ruReports,
    workspace: ruWorkspace,
    apps: ruApps,
    registration: ruRegistration,
    marketplace: ruMarketplace,
    docs: ruDocs,
  },
};

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: 'ru',
    defaultNS: 'common',
    ns: [
      'common',
      'users',
      'products',
      'security',
      'attachments',
      'languages',
      'partners',
      'sales',
      'leads',
      'company',
      'chat',
      'cron',
      'system_settings',
      'tasks',
      'activity',
      'saved_filters',
      'reports',
      'workspace',
      'apps',
      'registration',
      'marketplace',
      'docs',
    ],

    interpolation: {
      escapeValue: false, // React уже экранирует
    },

    detection: {
      // Порядок определения языка
      order: ['localStorage', 'navigator'],
      // Ключ в localStorage
      lookupLocalStorage: 'i18nextLng',
      // Кэшировать язык
      caches: ['localStorage'],
    },
  });

// Синхронизация dayjs-локали с i18next.
// Mantine DateTimePicker использует dayjs под капотом — без этого месяцы
// и дни недели остаются английскими независимо от пропса `locale`.
const syncDayjsLocale = (lng: string) => {
  // i18next может отдать 'en-US', dayjs знает 'en' — берём первую часть
  const short = (lng || 'en').split('-')[0];
  dayjs.locale(short);
};
syncDayjsLocale(i18n.language);
i18n.on('languageChanged', syncDayjsLocale);

export default i18n;
