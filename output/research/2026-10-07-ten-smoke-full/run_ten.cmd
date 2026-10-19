@echo off
rem The ten smoke questions through today's build, all the way: retrieval, answers, judging.
cd /d C:\Coding\exjobbet\GRAG-Job
set LOG=output\research\2026-10-07-ten-smoke-full\run.log
set PYTHONUNBUFFERED=1
set PYTHONIOENCODING=utf-8
set RAGAS_JUDGE_INFLIGHT=8
echo started %date% %time% > "%LOG%"
.venv\Scripts\python.exe prod\run.py --arm artefact_v4 --set 10smoke --char-budget 72000 --workers 6 --out "output\k=chars\artefact_v4__10smoke__cb72000__20261007T093000Z" >> "%LOG%" 2>&1
echo python exit code %errorlevel% >> "%LOG%"
echo finished %date% %time% >> "%LOG%"
