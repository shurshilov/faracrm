import { crudApi as api } from '@/services/api/crudApi';
import { API_BASE_URL } from '@/services/baseQueryWithReauth';

// Категории приложений — как в Selection модели marketplace_app.
export const CATEGORIES = [
  'crm',
  'communication',
  'telephony',
  'integration',
  'reports',
  'other',
];

export interface MarketVendor {
  id: number;
  name: string;
}

export interface MarketApp {
  id: number;
  name: string;
  summary: string | null;
  category: string;
  version: string;
  price: number;
  downloads: number;
  vendor: MarketVendor | null;
  /** Первый скриншот — обложка карточки. */
  cover_id: number | null;
}

export interface MarketAppDetail extends MarketApp {
  description: string | null;
  screenshots: { id: number; name: string }[];
}

export interface MarketListArgs {
  search?: string;
  category?: string;
  free?: boolean;
  sort?: 'popular' | 'new' | 'price';
}

export interface BuyResult {
  purchase_id: number;
  state: 'pending' | 'paid';
  /** Ссылка на оплату — только для платных и ещё не оплаченных. */
  payment_url: string | null;
}

export interface VendorStat {
  id: number;
  name: string;
  price: number;
  published: boolean;
  downloads: number;
  purchases: number;
  revenue: number;
}

/** Скриншот приложения — публичный роут, без авторизации. */
export function marketImageUrl(
  appId: number,
  attachmentId: number,
  width?: number,
  height?: number,
): string {
  const params = new URLSearchParams();
  if (width) params.set('w', String(width));
  if (height) params.set('h', String(height));
  const qs = params.toString();
  const base = `${API_BASE_URL}/marketplace/apps/${appId}/image/${attachmentId}`;
  return qs ? `${base}?${qs}` : base;
}

/** Архив модуля — авторизация кукой, открывается как обычная ссылка. */
export function marketDownloadUrl(appId: number): string {
  return `${API_BASE_URL}/marketplace/apps/${appId}/download`;
}

const marketplaceApi = api.injectEndpoints({
  endpoints: build => ({
    listMarketApps: build.query<{ data: MarketApp[] }, MarketListArgs>({
      query: args => ({
        url: '/marketplace/apps',
        params: {
          // paramsSerializer не кодирует значения — кодируем поиск сами.
          ...(args.search && { search: encodeURIComponent(args.search) }),
          ...(args.category && { category: args.category }),
          ...(args.free !== undefined && { free: args.free }),
          ...(args.sort && { sort: args.sort }),
        },
      }),
    }),

    getMarketApp: build.query<{ data: MarketAppDetail }, number>({
      query: appId => `/marketplace/apps/${appId}`,
    }),

    buyMarketApp: build.mutation<{ data: BuyResult }, number>({
      query: appId => ({
        url: `/marketplace/apps/${appId}/buy`,
        method: 'POST',
      }),
    }),

    getMarketStats: build.query<{ data: VendorStat[] }, void>({
      query: () => '/marketplace/my/stats',
    }),
  }),
});

export const {
  useListMarketAppsQuery,
  useGetMarketAppQuery,
  useBuyMarketAppMutation,
  useGetMarketStatsQuery,
} = marketplaceApi;
