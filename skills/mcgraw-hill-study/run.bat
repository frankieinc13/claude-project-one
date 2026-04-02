@echo off
REM McGraw Hill Study Agent launcher
REM Usage:
REM   run.bat "Business Law"
REM   run.bat "Business Strategies" --assignment "Chapter 3"
REM   run.bat "Business Law" --headless

cd /d "%~dp0"
python agent.py %*
pause
