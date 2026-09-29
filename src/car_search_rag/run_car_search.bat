@echo off
cd /d "%~dp0" || exit /b 1
python car_search\coffee_search.py
exit /b %errorlevel%
