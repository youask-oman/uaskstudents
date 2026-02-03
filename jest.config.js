module.exports = {
    preset: 'ts-jest',
    testEnvironment: 'jsdom',
    transform: {
        '^.+\\.tsx?$': ['ts-jest', {
            tsconfig: {
                jsx: 'react-jsx'
            }
        }],
    },
    testPathIgnorePatterns: [
        "<rootDir>/src/lib/__tests__"
    ],
    setupFilesAfterEnv: [
        "<rootDir>/jest.setup.ts"
    ],
    moduleNameMapper: {
        "^@/(.*)$": "<rootDir>/src/$1",
        "\\.(css|less|scss|sass)$": "<rootDir>/__mocks__/styleMock.js"
    },
};
