import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import type { Session } from '@services/auth/types';
import { RootState } from '@store/store';

type AuthState = {
  session?: Session;
};

const initialState: AuthState = {
  session: undefined,
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

    logOut: () => {
      localStorage.setItem('session', '');
      return initialState;
    },
  },
});

export const { setSession, storeSession, logOut, getSession } = slice.actions;

export default slice.reducer;

export const selectCurrentSession = (state: RootState) => state.auth.session;
export const selectIsLoggedIn = (state: RootState) => state.auth.session?.token;
