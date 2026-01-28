import { baseQuery } from '@services/baseQueryWithReauth';
import { createApi } from '@reduxjs/toolkit/query/react';
import type { Session, UserInput } from './types';

// const baseQuery = fetchBaseQuery({
//   baseUrl: '/',
//   prepareHeaders: headers => {
//     headers.set('Content-Type', 'application/json');
//     headers.set('Accept', 'application/json');
//     return headers;
//   },
//   // Example: we have a backend API always returns a 200,
//   // but sets an `isError` property when there is an error.
//   validateStatus: (response, result) =>
//     response.status === 200 && !result.error,
// });

export const authApi = createApi({
  reducerPath: 'authApi',
  baseQuery,
  endpoints: builder => ({
    login: builder.mutation<Session, UserInput>({
      query: props => ({
        url: '/signin',
        method: 'POST',
        // credentials: 'omit',
        body: {
          login: props.login,
          password: props.password,
        },
      }),

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      // transformResponse: (response: any) =>
      // create session
      // const session: Session = {};
      // response.data = session;
      // response.data,
    }),
  }),
});

export const { useLoginMutation } = authApi;
