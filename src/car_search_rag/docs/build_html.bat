@echo off
setlocal
set "DOCS_DIR=%~dp0"
pushd "%DOCS_DIR%" || exit /b 1

python -m sphinx -M clean source build
if errorlevel 1 goto :failed

python -m sphinx -M html source build -n -W --keep-going
if errorlevel 1 goto :failed

echo HTML documentation: %DOCS_DIR%build\html\index.html
popd
exit /b 0

:failed
popd
exit /b 1
