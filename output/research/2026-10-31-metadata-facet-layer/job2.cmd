@echo off
rem The rest of the facet layer's metadata edges, one step after the other, one process at a time.
rem Step 1 (the 574 edges encoded) finished in job.cmd; step 2 was stopped and is run again whole.
cd /d A:\exjobbet\grag_setup\facet_layer
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
set HF_HOME=A:\exjobbet\hf_cache
set HF_HUB_CACHE=A:\exjobbet\hf_cache\hub
set TRANSFORMERS_CACHE=A:\exjobbet\hf_cache\hub
set HF_HUB_DISABLE_SYMLINKS_WARNING=1
set TMP=A:\exjobbet\tmp
set TEMP=A:\exjobbet\tmp
set W=A:\exjobbet\grag_setup\facet_layer\work
set EXTRACT=A:\exjobbet\facet_pairs\fullcache_work\extract_standalone.py
set PYOLD=A:\exjobbet\repo\.venv\Scripts\python.exe
set PYNEW=A:\exjobbet\GRAG-Job\.venv\Scripts\python.exe

echo === 3 refits %date% %time% >> job2.log
"%PYNEW%" -u "%W%\test\graph\facet_pairs\metadata_edges.py" refits >> job2.log 2>> job2.err.log || (echo FAILED 3 >> job2.log & exit /b 1)

echo === 4 extend %date% %time% >> job2.log
"%PYNEW%" -u "%W%\test\graph\facet_pairs\metadata_edges.py" extend >> job2.log 2>> job2.err.log || (echo FAILED 4 >> job2.log & exit /b 1)
echo done > job2.layer_finished

echo === 2 encode shard 5 again, from a clean folder %date% %time% >> job2.log
if exist shard5_again rmdir /s /q shard5_again
mkdir shard5_again
"%PYOLD%" -u "%EXTRACT%" --edges "A:\exjobbet\facet_pairs\fullcache_work\edges.shard5.jsonl" --rows "A:\exjobbet\facet_pairs\fullcache_work\rows_export.jsonl.gz" --out "A:\exjobbet\grag_setup\facet_layer\shard5_again" --device cuda --flush 1024 --max-batch 8 --only gte-reranker-modernbert >> job2.log 2>> job2.err.log || (echo FAILED 2 >> job2.log & exit /b 1)

echo === 5 shard check %date% %time% >> job2.log
"%PYNEW%" -u research\shard_check.py --stored "A:\exjobbet\facet_pairs\fullcache\shard5\Alibaba-NLP__gte-reranker-modernbert-base.npz" --again "shard5_again\Alibaba-NLP__gte-reranker-modernbert-base.npz" --refits "%W%\output\facet_pairs\rounds\round1\metadata_pool" --config "%W%\output\facet_pairs\rounds\round1\model\config.json" --code "%W%\test\graph\facet_pairs" --out research\shard_check.json >> job2.log 2>> job2.err.log || (echo FAILED 5 >> job2.log & exit /b 1)

echo === done %date% %time% >> job2.log
echo done > job2.finished
