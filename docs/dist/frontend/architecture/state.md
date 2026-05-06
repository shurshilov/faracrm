# State Management

Redux Toolkit + RTK Query для серверного состояния и кэширования.

## Store

```typescript title="frontend/src/store/store.ts"
import { configureStore } from '@reduxjs/toolkit';
import { combineReducers } from 'redux';
import { crudApi } from '@services/api/crudApi';
import { authApi } from '@services/auth/auth';
import authSlice from '@slices/authSlice';

const reducers = combineReducers({
    [crudApi.reducerPath]: crudApi.reducer,
    [authApi.reducerPath]: authApi.reducer,
    auth: authSlice,
});

export const store = configureStore({
    reducer: reducers,
    middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware()
            .concat(crudApi.middleware)
            .concat(authApi.middleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
```

## RTK Query

Главная идея: **серверное состояние — через RTK Query** (автокэширование, инвалидация). **Клиентское состояние — через slices** (auth, UI state).

### crudApi — универсальный CRUD

Один API-клиент для всех моделей:

```typescript title="frontend/src/services/api/crudApi.ts"
export const crudApi = createApi({
    reducerPath: 'crudApi',
    baseQuery: baseQueryWithReauth,
    tagTypes: ['Fields', 'SavedFilters', 'Chat'],
    endpoints: build => ({

        search: build.query<GetListResult, GetListParams>({
            query: (arg) => ({
                method: 'POST',
                url: `/${arg.model}/search`,
                body: {
                    filter: arg.filter,
                    fields: arg.fields,
                    limit: arg.limit,
                    order: arg.order,
                    sort: arg.sort,
                },
            }),
        }),

        read: build.query<ReadResult, ReadParams>({
            query: (arg) => ({
                url: `/${arg.model}/read/${arg.id}`,
                params: { fields: arg.fields?.join(',') },
            }),
        }),

        create: build.mutation<CreateResult, CreateParams>({
            query: (arg) => ({
                method: 'POST',
                url: `/${arg.model}/create`,
                body: arg.data,
            }),
        }),

        edit: build.mutation<EditResult, EditParams>({
            query: (arg) => ({
                method: 'PATCH',
                url: `/${arg.model}/update/${arg.id}`,
                body: arg.data,
            }),
        }),

        deleteList: build.mutation<DeleteListResult, DeleteListParams>({
            query: (arg) => ({
                method: 'DELETE',
                url: `/${arg.model}/delete`,
                body: { ids: arg.ids },
            }),
        }),
    }),
});
```

### Использование в компонентах

```tsx
import { crudApi } from '@services/api/crudApi';

function ProductList() {
    const { data, isLoading } = crudApi.useSearchQuery({
        model: 'products',
        filter: [['active', '=', true]],
        fields: ['id', 'name', 'price'],
        limit: 20,
    });

    if (isLoading) return <Loader />;

    return (
        <DataTable
            records={data?.data ?? []}
            columns={[
                { accessor: 'name', title: 'Название' },
                { accessor: 'price', title: 'Цена' },
            ]}
        />
    );
}
```

## Auth Slice

```typescript title="frontend/src/slices/authSlice.ts"
const authSlice = createSlice({
    name: 'auth',
    initialState: { token: null, user: null },
    reducers: {
        setCredentials: (state, action) => {
            state.token = action.payload.token;
            state.user = action.payload.user;
        },
        logout: (state) => {
            state.token = null;
            state.user = null;
        },
    },
});
```
