@echo off
setlocal
python "%~dp0build_docs.py"
exit /b %errorlevel%
