$ErrorActionPreference = "Stop"
$env:TS_NODE_COMPILER_OPTIONS = '{"module":"CommonJS","moduleResolution":"node"}'

npx -q ts-node --transpile-only scripts/validate-templates.ts

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
