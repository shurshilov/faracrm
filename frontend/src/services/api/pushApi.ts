import { crudApi as api } from './crudApi';

// === Types ===

interface PushStatusResponse {
  available: boolean;
}

interface VapidKeyResponse {
  vapid_public_key: string | null;
}

interface PushSubscribeArgs {
  endpoint: string;
  keys: Record<string, string>;
}

interface PushSubscribeResponse {
  success: boolean;
  message: string;
}

// === API ===

const pushApi = api.injectEndpoints({
  endpoints: build => ({
    getPushStatus: build.query<PushStatusResponse, void>({
      query: () => '/web-push/status',
    }),

    getVapidKey: build.query<VapidKeyResponse, void>({
      query: () => '/web-push/vapid-key',
    }),

    pushSubscribe: build.mutation<PushSubscribeResponse, PushSubscribeArgs>({
      query: body => ({
        url: '/web-push/subscribe',
        method: 'POST',
        body,
      }),
    }),

    pushUnsubscribe: build.mutation<PushSubscribeResponse, PushSubscribeArgs>({
      query: body => ({
        url: '/web-push/unsubscribe',
        method: 'POST',
        body,
      }),
    }),
  }),
});

export const {
  useGetPushStatusQuery,
  useLazyGetVapidKeyQuery,
  usePushSubscribeMutation,
  usePushUnsubscribeMutation,
} = pushApi;
