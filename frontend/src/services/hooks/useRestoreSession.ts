import { useLayoutEffect } from 'react';
import { useDispatch } from 'react-redux';
import { Session } from '@services/auth/types';
import { setSession } from '@slices/authSlice';

export const useRestoreSession = () => {
  const dispatch = useDispatch();
  useLayoutEffect(() => {
    const restoreSession = async () => {
      const sessionPersist = JSON.parse(
        (await localStorage.getItem('session')) || '{}',
      ) as Session;

      if (sessionPersist) {
        dispatch(setSession({ session: sessionPersist }));
      }
    };

    restoreSession();
  }, [dispatch]);
};
