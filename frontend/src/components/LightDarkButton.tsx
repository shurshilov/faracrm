import { ActionIcon, Button, useMantineColorScheme } from '@mantine/core';
import { IconSun, IconMoon } from '@tabler/icons-react';

function LightAndDarkModeButton() {
  const { colorScheme, toggleColorScheme } = useMantineColorScheme();
  const dark = colorScheme === 'dark';

  return (
    <ActionIcon
      size="sm"
      variant="outline"
      color={dark ? 'gray' : 'blue'}
      onClick={() => toggleColorScheme()}
      title="Toggle color scheme">
      {dark ? (
        <IconMoon style={{ width: 18, height: 18 }} />
      ) : (
        <IconSun style={{ width: 18, height: 18 }} />
      )}
    </ActionIcon>
    // <Button size="xs" variant="link" onClick={toggleColorScheme}>
    //   {dark ? <IconSun /> : <IconMoon />}
    // </Button>
  );
}
export default LightAndDarkModeButton;
