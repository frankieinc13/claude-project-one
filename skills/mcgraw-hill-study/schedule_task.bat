@echo off
REM Creates a Windows Task Scheduler job to run the agent on a schedule.
REM Edit the TIME and COURSE variables below, then run this file as Administrator.

SET COURSE=Business Law
SET TIME=20:00
SET DAY=SUN
SET SCRIPT_DIR=%~dp0

echo Creating scheduled task for "%COURSE%" at %TIME% every %DAY%...

schtasks /create /tn "McGrawHillStudyAgent_%COURSE: =_%" ^
  /tr "python \"%SCRIPT_DIR%agent.py\" \"%COURSE%\" --headless" ^
  /sc WEEKLY /d %DAY% /st %TIME% ^
  /f

echo.
echo Task created. To view: schtasks /query /tn "McGrawHillStudyAgent_%COURSE: =_%"
echo To delete:  schtasks /delete /tn "McGrawHillStudyAgent_%COURSE: =_%" /f
pause
