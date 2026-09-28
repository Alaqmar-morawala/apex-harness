@echo off
setlocal
set "SCRIPT=%~dp0apex_harness.py"
where py >nul 2>nul
if %errorlevel%==0 (
    py "%SCRIPT%" %*
) else (
    python "%SCRIPT%" %*
)
