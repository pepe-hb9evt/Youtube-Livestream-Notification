@echo off
REM Manual start of the monitor (development phase).
REM Usage: run_monitor.bat [--dry-run | --test-mail | --reset | --status]
REM This file lives in the config folder: switch to the project root (parent folder).
cd /d "%~dp0.."
python ut_livestream_monitor.py %*
echo.
echo Exit code: %ERRORLEVEL%
pause
