@echo off
rem The desktop graph, phase B: the writer's write and verify, then the state after.
cd /d A:\exjobbet\GRAG-Job
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
set NEO4J_DATABASE=herb-eval-volmax
set PYTHONPATH=A:\exjobbet\GRAG-Job\prod;A:\exjobbet\GRAG-Job\test
set PY=A:\exjobbet\GRAG-Job\.venv\Scripts\python.exe
set F=A:\exjobbet\grag_setup\facet_layer
set L=%F%\graph_b.log
set CHECK_REPO=A:\exjobbet\GRAG-Job
set CHECK_MIRROR=%F%\work
set WRITER=%F%\work\test\graph\write_facet_layer.py
set B=A:\exjobbet\GRAG-Job\output\facet_weight_backup

echo === write %date% %time% >> %L%
"%PY%" -u %WRITER% write >> %L% 2>&1 || (echo FAILED write >> %L% & exit /b 1)
echo === verify %date% %time% >> %L%
"%PY%" -u %WRITER% verify >> %L% 2>&1 || (echo FAILED verify >> %L% & exit /b 1)
echo === check after %date% %time% >> %L%
"%PY%" -u %F%\check_layer.py --backup %B%\herb-eval-volmax__pilot_full_herb\weights.jsonl --out %F%\desktop_after.json >> %L% 2>&1 || (echo FAILED check >> %L% & exit /b 1)
echo === done %date% %time% >> %L%
echo done > %F%\graph_b.finished
