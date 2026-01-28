module.exports = {
  env: {
    browser: true,
    es2021: true,
  },
  ignorePatterns: [
    'js',
    '*.cjs',
    '*.mjs',
    '*.d.ts',
    '*.d.mts',
    'vite.config.ts',
  ],
  extends: [
    'mantine',
    'plugin:react/recommended',
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
  ],
  parserOptions: {
    project: './frontend/tsconfig.json',
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
  rules: {
    // https://eslint.org/docs/latest/rules/curly
    curly: ['error', 'all'],
    'react/react-in-jsx-scope': 'off',
  },
};
