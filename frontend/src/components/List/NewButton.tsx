import { Button } from '@mantine/core';
import { useNavigate } from 'react-router-dom';

export function NewButton() {
  const navigate = useNavigate();
  return (
    <Button variant="filled" onClick={() => navigate('create')}>
      New
    </Button>
  );
}
