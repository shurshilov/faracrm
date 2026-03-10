import { useState, useEffect, useCallback } from 'react';
import { API_BASE_URL } from '@/services/baseQueryWithReauth';

interface PushState {
  isSupported: boolean;
  isSubscribed: boolean;
  isLoading: boolean;
  permission: NotificationPermission | 'unsupported';
}

export function usePushNotifications() {
  const [state, setState] = useState<PushState>({
    isSupported: false,
    isSubscribed: false,
    isLoading: true,
    permission: 'unsupported',
  });

  useEffect(() => {
    const check = async () => {
      const ok =
        'serviceWorker' in navigator &&
        'PushManager' in window &&
        'Notification' in window;
      if (!ok) {
        setState({
          isSupported: false,
          isSubscribed: false,
          isLoading: false,
          permission: 'unsupported',
        });
        return;
      }
      const perm = Notification.permission;
      let sub = false;
      try {
        const r = await navigator.serviceWorker.getRegistration('/sw.js');
        if (r) {
          const s = await r.pushManager.getSubscription();
          sub = !!s;
        }
      } catch {}
      setState({
        isSupported: true,
        isSubscribed: sub,
        isLoading: false,
        permission: perm,
      });
    };
    check();
  }, []);

  const subscribe = useCallback(async () => {
    setState(s => ({ ...s, isLoading: true }));
    try {
      const vr = await fetch(API_BASE_URL + '/web-push/vapid-key', {
        credentials: 'include',
      });
      const { vapid_public_key } = await vr.json();
      if (!vapid_public_key) throw new Error('Web Push not configured');
      const perm = await Notification.requestPermission();
      if (perm !== 'granted') {
        setState(s => ({ ...s, isLoading: false, permission: perm }));
        return false;
      }
      const reg = await navigator.serviceWorker.register('/sw.js');
      await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: vapid_public_key,
      });
      const j = sub.toJSON();
      const r = await fetch(API_BASE_URL + '/web-push/subscribe', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ endpoint: j.endpoint, keys: j.keys }),
      });
      const res = await r.json();
      setState({
        isSupported: true,
        isSubscribed: res.success,
        isLoading: false,
        permission: 'granted',
      });
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
      const j = sub.toJSON();
      await fetch(API_BASE_URL + '/web-push/unsubscribe', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ endpoint: j.endpoint, keys: j.keys }),
      });
      await sub.unsubscribe();
      setState({
        isSupported: true,
        isSubscribed: false,
        isLoading: false,
        permission: Notification.permission,
      });
      return true;
    } catch (e) {
      console.error('[WebPush] Unsubscribe failed:', e);
      setState(s => ({ ...s, isLoading: false }));
      return false;
    }
  }, []);

  return { ...state, subscribe, unsubscribe };
}
