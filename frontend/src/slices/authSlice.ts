import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import type { Session } from '@services/auth/types';
import { RootState } from '@store/store';
import { API_BASE_URL } from '@services/baseQueryWithReauth';

type AuthState = {
  session?: Session;
};

function loadSession(): Session | undefined {
  try {
    const raw = localStorage.getItem('session');
    if (!raw) return undefined;
    const parsed = JSON.parse(raw);
    // Проверяем что это валидная сессия, а не пустой объект
    return parsed?.token ? (parsed as Session) : undefined;
  } catch {
    return undefined;
  }
}

/**
 * Серверный logout — деактивирует сессию в БД и удаляет guard cookie.
 * Fire-and-forget: не ждём ответа, не блокируем UI.
 */
function serverLogout(token?: string) {
  if (!token) return;
  try {
    fetch(`${API_BASE_URL}/sessions/logout`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      credentials: 'include',
    }).catch(() => {});
  } catch {
    // ignore
  }
}

const initialState: AuthState = {
  session: loadSession(),
};

const slice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    setSession: (
      state,
      { payload: { session } }: PayloadAction<{ session: Session }>,
    ) => {
      state.session = session;
    },

    getSession: state => {
      const sessionPersist = JSON.parse(
        localStorage.getItem('session') || '{}',
      ) as Session;
      // console.log(sessionPersist);
      if (sessionPersist) {
        state.session = sessionPersist;
      }
    },

    storeSession: (
      state,
      { payload: { session } }: PayloadAction<{ session: Session }>,
    ) => {
      localStorage.setItem('session', JSON.stringify(session));
      state.session = session;
    },

    logOut: state => {
      // Деактивируем сессию на сервере (fire-and-forget)
      serverLogout(state.session?.token);
      localStorage.setItem('session', '');
      return { session: undefined };
    },
  },
});

export const { setSession, storeSession, logOut, getSession } = slice.actions;

export default slice.reducer;

export const selectCurrentSession = (state: RootState) => state.auth.session;
export const selectIsLoggedIn = (state: RootState) => state.auth.session?.token;
