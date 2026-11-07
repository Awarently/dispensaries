@echo off
rem Wrapper for Windows Task Scheduler. Runs from this folder and appends to run.log.
cd /d "%~dp0"
python run.py >> run.log 2>&1
