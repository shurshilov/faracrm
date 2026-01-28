/**
 * Cron API - дополнительные endpoints для cron_job
 * Использует injectEndpoints в общий crudApi
 */

import { crudApi } from '@services/api/crudApi';

const injectedRtkApi = crudApi.injectEndpoints({
  endpoints: build => ({
    runCronJob: build.mutation<RunCronJobResponse, number>({
      query: id => ({
        url: `/cron_job/${id}/run`,
        method: 'POST',
      }),
    }),
    toggleCronJob: build.mutation<ToggleCronJobResponse, number>({
      query: id => ({
        url: `/cron_job/${id}/toggle`,
        method: 'PATCH',
      }),
    }),
  }),
  overrideExisting: false,
});

export type RunCronJobResponse = {
  success: boolean;
  status?: string;
  error?: string;
  duration?: number;
};

export type ToggleCronJobResponse = {
  success: boolean;
  active: boolean;
};

export const { useRunCronJobMutation, useToggleCronJobMutation } =
  injectedRtkApi;
