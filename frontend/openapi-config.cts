import type { ConfigFile } from '@rtk-query/codegen-openapi';

// Настройки автогенерации RTK-query апишки по свагеру бекенда CLIENT PORTAL 3
const config: ConfigFile = {
  schemaFile: 'http://127.0.0.1:8090/openapi.json',
  apiFile: './src/services/api/crudApi.ts',
  apiImport: 'crudApi',
  exportName: 'crudApi',
  outputFiles: {
    './src/services/api/users.ts': {
      filterEndpoints: [/users/i],
    },
    './src/services/api/access_list.ts': {
      filterEndpoints: [/accessList/i],
    },
    './src/services/api/models.ts': {
      filterEndpoints: [/models/i],
    },
    './src/services/api/roles.ts': {
      filterEndpoints: [/roles/i],
    },
    './src/services/api/rules.ts': {
      filterEndpoints: [/rules/i],
    },
    './src/services/api/sessions.ts': {
      filterEndpoints: [/sessions/i],
    },
    './src/services/api/attachments.ts': {
      filterEndpoints: [/attachments/i],
    },
    './src/services/api/attachments_storage.ts': {
      filterEndpoints: [/attachments_storage/i],
    },
    './src/services/api/partner.ts': {
      filterEndpoints: [/partner/i],
    },
    './src/services/api/lead.ts': {
      filterEndpoints: [/lead/i],
    },
    './src/services/api/team_crm.ts': {
      filterEndpoints: [/team_crm/i],
    },
    './src/services/api/category.ts': {
      filterEndpoints: [/category/i],
    },
    './src/services/api/product.ts': {
      filterEndpoints: [/product/i],
    },
    './src/services/api/uoms.ts': {
      filterEndpoints: [/uom/i],
    },
    './src/services/api/sale_line.ts': {
      filterEndpoints: [/sale_line/i],
    },
    './src/services/api/sale.ts': {
      filterEndpoints: [/sale/i],
    },
    './src/services/api/tax.ts': {
      filterEndpoints: [/tax/i],
    },
  },
  hooks: { queries: true, lazyQueries: true, mutations: true },
  // endpointOverrides: [{ type: 'query', pattern: 'route*IdPost' }],
};

export default config;
