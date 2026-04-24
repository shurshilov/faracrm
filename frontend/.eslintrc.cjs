module.exports = {
  env: {
    browser: true,
    es2021: true,
  },
  ignorePatterns: [
    'dist',
    'node_modules',
    'js',
    '*.cjs',
    '*.mjs',
    '*.d.ts',
    '*.d.mts',
    'vite.config.ts',
  ],
  extends: [
    'plugin:react/recommended',
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'mantine', // Ставим после реакта, чтобы применить правила Mantine
    'prettier', // Отключает конфликтующие правила форматирования
  ],
  parserOptions: {
    project: './tsconfig.json',
  },
  plugins: [
    'react',
    'jsx-a11y',
    'react-hooks',
    'react-refresh',
    'promise',
    'import',
    'prettier',
  ],
  settings: {
    react: { version: 'detect' }, // Чтобы ESLint знал версию React
  },
  rules: {
    // https://eslint.org/docs/latest/rules/curly
    curly: ['error', 'all'],
    'react/react-in-jsx-scope': 'off',
  },
};
