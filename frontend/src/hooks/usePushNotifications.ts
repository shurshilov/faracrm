/**
 * usePushNotifications - Web Push subscription management.
 *
 * Uses RTK Query for API calls (auto token via baseQueryWithReauth).
 * Checks /web-push/status to show/hide toggle.
 */

import { useState, useEffect, useCallback } from 'react';
import {
  useGetPushStatusQuery,
  useLazyGetVapidKeyQuery,
  usePushSubscribeMutation,
  usePushUnsubscribeMutation,
} from '@/services/api/pushApi';

export function usePushNotifications() {
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [permission, setPermission] = useState<
    NotificationPermission | 'unsupported'
  >('unsupported');

  const isSupported =
    typeof window !== 'undefined' &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window;

  // Server status
  const { data: statusData, isLoading: statusLoading } = useGetPushStatusQuery(
    undefined,
    { skip: !isSupported },
  );
  const isAvailable = statusData?.available === true;

  // RTK Query mutations & lazy query
  const [getVapidKey] = useLazyGetVapidKeyQuery();
  const [subscribeMutation] = usePushSubscribeMutation();
  const [unsubscribeMutation] = usePushUnsubscribeMutation();

  // Check browser subscription on mount
  useEffect(() => {
    if (!isSupported) {
      setIsLoading(false);
      return;
    }

    const check = async () => {
      setPermission(Notification.permission);
      try {
        const reg = await navigator.serviceWorker.getRegistration('/sw.js');
        if (reg) {
          const sub = await reg.pushManager.getSubscription();
          setIsSubscribed(!!sub);
        }
      } catch {}
      setIsLoading(false);
    };

    check();
  }, [isSupported]);

  const subscribe = useCallback(async () => {
    setIsLoading(true);
    try {
      // 1. Get VAPID key via RTK Query
      const { data: vapidData } = await getVapidKey();
      if (!vapidData?.vapid_public_key)
        throw new Error('Web Push not configured');

      // 2. Request permission
      const perm = await Notification.requestPermission();
      setPermission(perm);
      if (perm !== 'granted') {
        setIsLoading(false);
        return false;
      }

      // 3. Register SW & subscribe
      const reg = await navigator.serviceWorker.register('/sw.js');
      await navigator.serviceWorker.ready;

      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: vapidData.vapid_public_key,
      });

      // 4. Send to backend via RTK Query
      const j = sub.toJSON();
      const result = await subscribeMutation({
        endpoint: j.endpoint!,
        keys: j.keys as Record<string, string>,
      }).unwrap();

      setIsSubscribed(result.success);
      setIsLoading(false);
      return result.success;
    } catch (e) {
      console.error('[WebPush] Subscribe failed:', e);
      setIsLoading(false);
      return false;
    }
  }, [getVapidKey, subscribeMutation]);

  const unsubscribe = useCallback(async () => {
    setIsLoading(true);
    try {
      const reg = await navigator.serviceWorker.getRegistration('/sw.js');
      if (!reg) {
        setIsSubscribed(false);
        setIsLoading(false);
        return true;
      }

      const sub = await reg.pushManager.getSubscription();
      if (!sub) {
        setIsSubscribed(false);
        setIsLoading(false);
        return true;
      }

      // Unsubscribe on server via RTK Query
      const j = sub.toJSON();
      await unsubscribeMutation({
        endpoint: j.endpoint!,
        keys: j.keys as Record<string, string>,
      }).unwrap();

      // Unsubscribe in browser
      await sub.unsubscribe();

      setIsSubscribed(false);
      setPermission(Notification.permission);
      setIsLoading(false);
      return true;
    } catch (e) {
      console.error('[WebPush] Unsubscribe failed:', e);
      setIsLoading(false);
      return false;
    }
  }, [unsubscribeMutation]);

  return {
    isSupported,
    isAvailable,
    isSubscribed,
    isLoading: isLoading || statusLoading,
    permission,
    subscribe,
    unsubscribe,
  };
}
