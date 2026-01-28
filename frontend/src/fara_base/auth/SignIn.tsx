import {
  Paper,
  TextInput,
  PasswordInput,
  Button,
  Title,
  Text,
} from '@mantine/core';
import * as yup from 'yup';
import { useForm, yupResolver } from '@mantine/form';
import { useDispatch } from 'react-redux';
import classes from './SignIn.module.css';
import { UserInput } from '@/services/auth/types';
import { useLoginMutation } from '@/services/auth/auth';
import { storeSession } from '@/slices/authSlice';

export default function SignIn() {
  const dispatch = useDispatch();
  const [login, { isLoading: loading }] = useLoginMutation();
  const validationSchema = yup.object({
    login: yup
      .string()
      .required('Login is required')
      .max(120, 'Login is too long'),
    password: yup.string().required('Password is required'),
  });

  const form = useForm({
    initialValues: {
      login: 'admin',
      password: '12345678!Aaa',
    },
    validate: yupResolver(validationSchema),
  });

  const onSubmitHandler = async (values: UserInput) => {
    try {
      // Using a query hook automatically fetches data and returns query values
      const session = await login(values).unwrap();
      dispatch(storeSession({ session }));
    } catch (err) {
      // Toast.error('Error login', JSON.stringify(err));
    } finally {
      // setLoading(false);
    }
  };

  return (
    <div>
      <form onSubmit={form.onSubmit(onSubmitHandler)}>
        <div className={classes.wrapper}>
          <Paper className={classes.form} radius={0} p={30}>
            <Title
              order={2}
              className={classes.title}
              ta="center"
              mt="md"
              mb={50}>
              Welcome to FARA CRM
            </Title>
            <Text ta="center" mt="md" mb={50}>
              To get more information about the template please check the{' '}
              <a href="https://github.com/auronvila/mantine-template/wiki">
                documentation
              </a>
            </Text>
            <TextInput
              {...form.getInputProps('login')}
              name="login"
              label="Login"
              withAsterisk
              placeholder="admin"
              size="md"
            />
            <PasswordInput
              {...form.getInputProps('password')}
              name="password"
              label="Password"
              placeholder="123"
              mt="md"
              size="md"
            />
            <Button loading={loading} type="submit" fullWidth mt="xl" size="md">
              Login
            </Button>
            {/*<Text ta="center" mt="md">*/}
            {/*  Don&apos;t have an account?{' '}*/}
            {/*  <Anchor<'a'> href="#" fw={700} onClick={(event) => event.preventDefault()}>*/}
            {/*    Register*/}
            {/*  </Anchor>*/}
            {/*</Text>*/}
          </Paper>
        </div>
      </form>
    </div>
  );
}
