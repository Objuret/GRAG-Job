@echo off
rem The hundred through the two query-side calls, retrieval only. While it runs the lid-close
rem action is "do nothing" (it was "sleep" on mains and on battery); it is set back at the end.
cd /d C:\Coding\exjobbet\GRAG-Job
set LOG=output\research\2026-10-07-second-call\run.log
powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0
powercfg /setdcvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0
powercfg /setactive SCHEME_CURRENT
set PYTHONUNBUFFERED=1
set PYTHONIOENCODING=utf-8
echo started %date% %time% > "%LOG%"
.venv\Scripts\python.exe prod\run.py --arm artefact_v4 --set gold --char-budget 72000 --workers 6 --retrieval-only --out "output\k=chars\artefact_v4__gold100__cb72000__20261007T041909Z" >> "%LOG%" 2>&1
echo python exit code %errorlevel% >> "%LOG%"
powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 1
powercfg /setdcvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 1
powercfg /setactive SCHEME_CURRENT
echo lid action set back, finished %date% %time% >> "%LOG%"
