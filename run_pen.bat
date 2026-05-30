@echo off
:: Change the directory to the location of this batch file
cd /d "%~dp0"

:: Launch the tool silently without a console window
start pythonw main.py