@echo off
rem The desktop graph, phase A: its state before, a backup by the clone's own tool, the writer's plan.
rem Nothing is written to the graph here.
cd /d A:\exjobbet\GRAG-Job
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
set NEO4J_DATABASE=herb-eval-volmax
set PYTHONPATH=A:\exjobbet\GRAG-Job\prod;A:\exjobbet\GRAG-Job\test
set PY=A:\exjobbet\GRAG-Job\.venv\Scripts\python.exe
set F=A:\exjobbet\grag_setup\facet_layer
set L=%F%\graph_a.log
set CHECK_REPO=A:\exjobbet\GRAG-Job
set CHECK_MIRROR=%F%\work
set WRITER=%F%\work\test\graph\write_facet_layer.py
set B=A:\exjobbet\GRAG-Job\output\facet_weight_backup

echo === check before %date% %time% >> %L%
"%PY%" -u %F%\check_layer.py --out %F%\desktop_before.json >> %L% 2>&1 || (echo FAILED check >> %L% & exit /b 1)
echo === keep the entry that is there %date% %time% >> %L%
if exist %B%\herb-eval-volmax__pilot_full_herb\manifest.json xcopy /e /i /q /y %B%\herb-eval-volmax__pilot_full_herb %B%\herb-eval-volmax__pilot_full_herb__kept-before-20261031 >> %L% 2>&1
echo === backup %date% %time% >> %L%
"%PY%" -u test\graph\backup_facet_weights.py backup >> %L% 2>&1 || (echo FAILED backup >> %L% & exit /b 1)
"%PY%" -u test\graph\backup_facet_weights.py verify >> %L% 2>&1 || (echo FAILED verify >> %L% & exit /b 1)
xcopy /e /i /q /y %B%\herb-eval-volmax__pilot_full_herb %B%\herb-eval-volmax__pilot_full_herb__before-metadata-edges-20261031-desktop >> %L% 2>&1
echo === plan %date% %time% >> %L%
"%PY%" -u %WRITER% plan >> %L% 2>&1 || (echo FAILED plan >> %L% & exit /b 1)
echo === done %date% %time% >> %L%
echo done > %F%\graph_a.finished
