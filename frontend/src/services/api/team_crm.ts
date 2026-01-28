import { crudApi as api } from './crudApi';
const injectedRtkApi = api.injectEndpoints({
  endpoints: build => ({}),
  overrideExisting: false,
});
export { injectedRtkApi as crudApi };
export const {} = injectedRtkApi;
