import { ActionIcon, useMantineColorScheme } from '@mantine/core';
import { IconLogout } from '@tabler/icons-react';
import { useDispatch } from 'react-redux';
import { logOut } from '@/slices/authSlice';
import { authApi, useLogoutMutation } from '@/services/auth/auth';

function LogoutButton() {
  const { colorScheme } = useMantineColorScheme();
  const dark = colorScheme === 'dark';
  const dispatch = useDispatch();
  const [triggerLogout] = useLogoutMutation();

  return (
    <ActionIcon
      size="sm"
      variant="outline"
      color={dark ? 'gray' : 'blue'}
      onClick={async () => {
        try {
          await triggerLogout().unwrap(); // Запрос на сервер
        } finally {
          // В любом случае чистим локальные данные
          dispatch(authApi.util.resetApiState());
          dispatch(logOut());
        }
        // отменяем активные запросы
        // dispatch(authApi.util.resetApiState());
        // dispatch(logOut());
      }}
      title="Toggle color scheme">
      <IconLogout style={{ width: 18, height: 18 }} />
    </ActionIcon>
  );
}
export default LogoutButton;
