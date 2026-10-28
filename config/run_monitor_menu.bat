@echo off
REM Interactive start menu for the monitor (development phase).
REM Asks which mode to run, then starts ut_livestream_monitor.py accordingly.
setlocal
REM This file lives in the config folder: switch to the project root (parent folder).
cd /d "%~dp0.."

:menu
cls
echo ============================================
echo   UT-Livestream-Notification - Start menu
echo ============================================
echo.
echo   1  Normal run                     (check feeds, mail on new entries)
echo   2  Dry run                        (check only, no mail, state unchanged)
echo   3  Test mail with last video list (state of the last run, no feed access)
echo   4  Reset                          (forget known videos, new baseline)
echo   5  Show log                       (logs\log-last-3-days.txt)
echo   6  Outage status                  (overview of feed errors per channel)
echo   7  Show options                   (all options of ut_livestream_monitor.py)
echo   0  Exit
echo.
choice /c 12345670 /n /m "Select [1-7, 0]: "
set "selection=%ERRORLEVEL%"

if "%selection%"=="1" set "args="
if "%selection%"=="2" set "args=--dry-run"
if "%selection%"=="3" set "args=--send-list"
if "%selection%"=="4" goto confirm_reset
if "%selection%"=="5" goto show_log
if "%selection%"=="6" set "args=--status"
if "%selection%"=="7" set "args=--help"
if "%selection%"=="8" goto end
goto run

:confirm_reset
echo.
choice /c yn /n /m "Really forget all known videos? [y/n]: "
if errorlevel 2 goto menu
set "args=--reset"
goto run

:show_log
echo.
if exist "logs\log-last-3-days.txt" (
    type "logs\log-last-3-days.txt" | more
) else (
    echo No log file yet.
)
echo.
pause
goto menu

:run
echo.
echo Running: python ut_livestream_monitor.py %args%
echo --------------------------------------------
python ut_livestream_monitor.py %args%
echo --------------------------------------------
echo Exit code: %ERRORLEVEL%
echo.
choice /c yn /n /m "Back to menu? [y/n]: "
if errorlevel 2 goto end
goto menu

:end
endlocal
