import {
  configureStore,
  combineReducers,
  UnknownAction,
} from '@reduxjs/toolkit';
// import {
//   persistReducer,
//   FLUSH,
//   REHYDRATE,
//   PAUSE,
//   PERSIST,
//   PURGE,
//   REGISTER,
// } from 'redux-persist';
import { setupListeners } from '@reduxjs/toolkit/query';
// import AsyncStorage from '@react-native-async-storage/async-storage';

import { crudApi } from '@services/api/crudApi';
import { authApi } from '@services/auth/auth';
import { configApi } from '@services/config/config';
import authSlice, { logOut } from '@slices/authSlice'; // Импортируем экшен логаута

// 1. Собираем базовые редьюсеры
const appReducer = combineReducers({
  [crudApi.reducerPath]: crudApi.reducer,
  [authApi.reducerPath]: authApi.reducer,
  [configApi.reducerPath]: configApi.reducer,
  auth: authSlice,
  // remaining reducers
});

// 2. Добавляем Root Reducer для сброса всего стейта при логауте
const rootReducer = (
  state: ReturnType<typeof appReducer> | undefined,
  action: UnknownAction,
) => {
  if (action.type === logOut.type) {
    // При получении экшена логаута передаем undefined во все дочерние редьюсеры,
    // что заставляет их вернуться к initialState (включая кэш API)
    state = undefined;
  }
  return appReducer(state, action);
};

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
      .concat(authApi.middleware)
      .concat(configApi.middleware),
  // .concat(apiErrorMiddleware),
  // NOTE this addition
  reducer: rootReducer, // Используем rootReducer вместо объекта reducers
});

setupListeners(store.dispatch); // NOTE this addition
export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
