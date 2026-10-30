@echo off
cd /d "%~dp0"
py -3 -m pip install --quiet -r requirements.txt
start "" pyw -3 run.py
