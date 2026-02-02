import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

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

// ============ Функция слияния переводов ============
type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};

function deepMerge<T extends Record<string, unknown>>(
  target: T,
  ...sources: DeepPartial<T>[]
): T {
  const result = { ...target };

  for (const source of sources) {
    for (const key in source) {
      const sourceValue = source[key];
      const targetValue = result[key];

      if (
        sourceValue &&
        typeof sourceValue === 'object' &&
        !Array.isArray(sourceValue) &&
        targetValue &&
        typeof targetValue === 'object' &&
        !Array.isArray(targetValue)
      ) {
        (result as Record<string, unknown>)[key] = deepMerge(
          targetValue as Record<string, unknown>,
          sourceValue as Record<string, unknown>,
        );
      } else if (sourceValue !== undefined) {
        (result as Record<string, unknown>)[key] = sourceValue;
      }
    }
  }

  return result;
}

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

export default i18n;
