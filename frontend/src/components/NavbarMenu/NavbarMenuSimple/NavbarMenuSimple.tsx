import { UnstyledButton } from '@mantine/core';
import { useLocation, useNavigate } from 'react-router-dom';
import classes from './NavbarMenuSimple.module.css';

interface NavbarMenuSimpleProps {
  children: React.ReactNode;
  to: string;
}

export function NavbarMenuSimple({ to, children }: NavbarMenuSimpleProps) {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <UnstyledButton
      className={classes.link}
      data-active={location.pathname === to ? 'true' : undefined}
      onClick={() => navigate(to)}>
      <span className={classes.label}>{children}</span>
    </UnstyledButton>
  );
}
