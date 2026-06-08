const nextJest = require('next/jest');

const createJestConfig = nextJest({ dir: './' });

const customConfig = {
  testEnvironment: 'jest-environment-jsdom',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.ts'],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
    'lightweight-charts': '<rootDir>/src/__mocks__/lightweight-charts.ts',
    'recharts': '<rootDir>/src/__mocks__/recharts.tsx',
  },
  testMatch: ['**/__tests__/**/*.{ts,tsx}', '**/*.test.{ts,tsx}'],
};

module.exports = createJestConfig(customConfig);
