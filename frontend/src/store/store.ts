// import {
//   persistReducer,
//   FLUSH,
//   REHYDRATE,
//   PAUSE,
//   PERSIST,
//   PURGE,
//   REGISTER,
// } from 'redux-persist';
import { configureStore } from '@reduxjs/toolkit';
import { combineReducers } from 'redux';

import { setupListeners } from '@reduxjs/toolkit/query';
// import AsyncStorage from '@react-native-async-storage/async-storage';

import { crudApi } from '@services/api/crudApi';
import { authApi } from '@services/auth/auth';
import authSlice from '@slices/authSlice';

const reducers = combineReducers({
  [crudApi.reducerPath]: crudApi.reducer,
  [authApi.reducerPath]: authApi.reducer,
  auth: authSlice,
  // remaining reducers
});

// const persistConfig = {
//   key: 'persistedReducer',
//   version: 4,
//   storage: AsyncStorage,
// };

// const persistedReducer = persistReducer(persistConfig, reducers);
// interface CustomStore extends Store<RootState, AnyAction> {
//   asyncReducers?: AsyncReducers
// }
export const store = configureStore({
  devTools: process.env.NODE_ENV === 'development',
  middleware: getDefaultMiddleware =>
    getDefaultMiddleware({
      // serializableCheck: {
      //   ignoredActions: [FLUSH, REHYDRATE, PAUSE, PERSIST, PURGE, REGISTER],
      // },
    })
      .concat(crudApi.middleware)
      .concat(authApi.middleware),
  // .concat(apiErrorMiddleware),
  // NOTE this addition
  reducer: reducers,
});

setupListeners(store.dispatch); // NOTE this addition
export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
