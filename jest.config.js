module.exports = {
    preset: 'ts-jest',
    testEnvironment: 'node',
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
};
