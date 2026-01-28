import { ActionIcon, useMantineColorScheme } from '@mantine/core';
import { IconLogout } from '@tabler/icons-react';
import { useDispatch } from 'react-redux';
import { logOut } from '@/slices/authSlice';
import { authApi } from '@/services/auth/auth';

function LogoutButton() {
  const { colorScheme } = useMantineColorScheme();
  const dark = colorScheme === 'dark';
  const dispatch = useDispatch();

  return (
    <ActionIcon
      size="sm"
      variant="outline"
      color={dark ? 'gray' : 'blue'}
      onClick={() => {
        dispatch(logOut());
        dispatch(authApi.internalActions?.resetApiState());
      }}
      title="Toggle color scheme">
      <IconLogout style={{ width: 18, height: 18 }} />
    </ActionIcon>
  );
}
export default LogoutButton;
