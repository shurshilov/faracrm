/**
 * CallButton — кнопка "Позвонить".
 *
 * Использование:
 *   <CallButton peer={{ id: user.id, name: user.name }} />                   // icon-only (для header)
 *   <CallButton peer={{ id: user.id, name: user.name }} showLabel />         // с подписью
 *   <CallButton peer={{ id: user.id, name: user.name }} fullWidth showLabel /> // для карточек
 *
 * В активном звонке / дозвоне — кнопка disabled (нельзя начать второй звонок).
 */
import { ActionIcon, Button, Tooltip } from '@mantine/core';
import { IconPhone } from '@tabler/icons-react';
import { useCall } from '../context/CallContext';

interface CallButtonProps {
  peer: { id: number; name: string };
  size?: 'xs' | 'sm' | 'md' | 'lg';
  variant?: 'filled' | 'light' | 'subtle';
  fullWidth?: boolean;
  /** Показать текстовую подпись. Дефолт false — только иконка. */
  showLabel?: boolean;
}

export function CallButton({
  peer,
  size = 'lg',
  variant = 'subtle',
  fullWidth = false,
  showLabel = false,
}: CallButtonProps) {
  const { state, startCall } = useCall();
  const busy = state !== 'idle' && state !== 'ended';

  const tooltipLabel = busy
    ? 'Завершите текущий звонок'
    : `Позвонить ${peer.name}`;

  if (!showLabel) {
    // Icon-only режим — для header'ов и плотных UI
    return (
      <Tooltip label={tooltipLabel} withArrow>
        <ActionIcon
          size={size}
          variant={variant}
          color="green"
          disabled={busy}
          onClick={() => startCall(peer)}
          title={tooltipLabel}>
          <IconPhone size={20} />
        </ActionIcon>
      </Tooltip>
    );
  }

  // Режим с подписью — для карточек и dropdown'ов
  return (
    <Tooltip label={tooltipLabel} withArrow disabled={!busy}>
      <Button
        size={size === 'lg' ? 'sm' : size}
        variant={variant === 'subtle' ? 'light' : variant}
        fullWidth={fullWidth}
        color="green"
        disabled={busy}
        leftSection={<IconPhone size={16} />}
        onClick={() => startCall(peer)}>
        Позвонить
      </Button>
    </Tooltip>
  );
}
