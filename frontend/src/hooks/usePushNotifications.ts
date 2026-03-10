/**
 * usePushNotifications - Web Push subscription management.
 *
 * Checks server /web-push/status to determine if push is configured.
 * If not configured (no active connector with VAPID keys) - isAvailable=false,
 * toggle is hidden in UI.
 */

import { useState, useEffect, useCallback } from 'react';
import { API_BASE_URL } from '@/services/baseQueryWithReauth';

interface PushState {
  /** Browser supports Push API */
  isSupported: boolean;
  /** Server has active configured web_push connector */
  isAvailable: boolean;
  /** Current browser is subscribed */
  isSubscribed: boolean;
  /** Loading state */
  isLoading: boolean;
  /** Notification permission */
  permission: NotificationPermission | 'unsupported';
}

export function usePushNotifications() {
  const [state, setState] = useState<PushState>({
    isSupported: false,
    isAvailable: false,
    isSubscribed: false,
    isLoading: true,
    permission: 'unsupported',
  });

  useEffect(() => {
    const check = async () => {
      // 1. Browser support
      const isSupported =
        'serviceWorker' in navigator &&
        'PushManager' in window &&
        'Notification' in window;

      if (!isSupported) {
        setState({
          isSupported: false,
          isAvailable: false,
          isSubscribed: false,
          isLoading: false,
          permission: 'unsupported',
        });
        return;
      }

      // 2. Server status - is connector configured?
      let isAvailable = false;
      try {
        const resp = await fetch(API_BASE_URL + '/web-push/status', {
          credentials: 'include',
        });
        const data = await resp.json();
        isAvailable = data.available === true;
      } catch {
        // Server unavailable or module not installed
      }

      // 3. Current subscription in browser
      const permission = Notification.permission;
      let isSubscribed = false;
      try {
        const reg = await navigator.serviceWorker.getRegistration('/sw.js');
        if (reg) {
          const sub = await reg.pushManager.getSubscription();
          isSubscribed = !!sub;
        }
      } catch {}

      setState({
        isSupported: true,
        isAvailable,
        isSubscribed,
        isLoading: false,
        permission,
      });
    };

    check();
  }, []);

  const subscribe = useCallback(async () => {
    setState(s => ({ ...s, isLoading: true }));
    try {
      // Get VAPID key
      const vr = await fetch(API_BASE_URL + '/web-push/vapid-key', {
        credentials: 'include',
      });
      const { vapid_public_key } = await vr.json();
      if (!vapid_public_key) throw new Error('Web Push not configured');

      // Request permission
      const perm = await Notification.requestPermission();
      if (perm !== 'granted') {
        setState(s => ({ ...s, isLoading: false, permission: perm }));
        return false;
      }

      // Register SW & subscribe
      const reg = await navigator.serviceWorker.register('/sw.js');
      await navigator.serviceWorker.ready;

      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: vapid_public_key,
      });

      // Send subscription to backend
      const j = sub.toJSON();
      const r = await fetch(API_BASE_URL + '/web-push/subscribe', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ endpoint: j.endpoint, keys: j.keys }),
      });
      const res = await r.json();

      setState(s => ({
        ...s,
        isSubscribed: res.success,
        isLoading: false,
        permission: 'granted',
      }));
      return res.success;
    } catch (e) {
      console.error('[WebPush] Subscribe failed:', e);
      setState(s => ({ ...s, isLoading: false }));
      return false;
    }
  }, []);

  const unsubscribe = useCallback(async () => {
    setState(s => ({ ...s, isLoading: true }));
    try {
      const reg = await navigator.serviceWorker.getRegistration('/sw.js');
      if (!reg) {
        setState(s => ({ ...s, isLoading: false, isSubscribed: false }));
        return true;
      }

      const sub = await reg.pushManager.getSubscription();
      if (!sub) {
        setState(s => ({ ...s, isLoading: false, isSubscribed: false }));
        return true;
      }

      // Unsubscribe on server
      const j = sub.toJSON();
      await fetch(API_BASE_URL + '/web-push/unsubscribe', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ endpoint: j.endpoint, keys: j.keys }),
      });

      // Unsubscribe in browser
      await sub.unsubscribe();

      setState(s => ({
        ...s,
        isSubscribed: false,
        isLoading: false,
        permission: Notification.permission,
      }));
      return true;
    } catch (e) {
      console.error('[WebPush] Unsubscribe failed:', e);
      setState(s => ({ ...s, isLoading: false }));
      return false;
    }
  }, []);

  return { ...state, subscribe, unsubscribe };
}
