@echo off
rem The facet layer's metadata edges, one step after the other, one process at a time.
rem The encoder runs with the full pass's own python, extractor and settings (out\fullcache.bat).
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
set C=%W%\output\facet_pairs\rounds\round1\metadata_pool\cache
set EXTRACT=A:\exjobbet\facet_pairs\fullcache_work\extract_standalone.py
set PYOLD=A:\exjobbet\repo\.venv\Scripts\python.exe
set PYNEW=A:\exjobbet\GRAG-Job\.venv\Scripts\python.exe

echo === 1 encode the metadata edges %date% %time% >> job.log
"%PYOLD%" -u "%EXTRACT%" --edges "%C%\edges.jsonl" --rows "%C%\rows.jsonl" --out "%C%" --device cuda --flush 1024 --max-batch 8 --only gte-reranker-modernbert >> job.log 2>> job.err.log || (echo FAILED 1 >> job.log & exit /b 1)
if not exist "%C%\Alibaba-NLP__gte-reranker-modernbert-base.npz" (echo FAILED 1 no npz >> job.log & exit /b 1)

echo === 2 encode shard 5 again %date% %time% >> job.log
"%PYOLD%" -u "%EXTRACT%" --edges "A:\exjobbet\facet_pairs\fullcache_work\edges.shard5.jsonl" --rows "A:\exjobbet\facet_pairs\fullcache_work\rows_export.jsonl.gz" --out "A:\exjobbet\grag_setup\facet_layer\shard5_again" --device cuda --flush 1024 --max-batch 8 --only gte-reranker-modernbert >> job.log 2>> job.err.log || (echo FAILED 2 >> job.log & exit /b 1)

echo === 3 refits %date% %time% >> job.log
"%PYNEW%" -u "%W%\test\graph\facet_pairs\metadata_edges.py" refits >> job.log 2>> job.err.log || (echo FAILED 3 >> job.log & exit /b 1)

echo === 4 extend %date% %time% >> job.log
"%PYNEW%" -u "%W%\test\graph\facet_pairs\metadata_edges.py" extend >> job.log 2>> job.err.log || (echo FAILED 4 >> job.log & exit /b 1)

echo === 5 shard check %date% %time% >> job.log
"%PYNEW%" -u research\shard_check.py --stored "A:\exjobbet\facet_pairs\fullcache\shard5\Alibaba-NLP__gte-reranker-modernbert-base.npz" --again "shard5_again\Alibaba-NLP__gte-reranker-modernbert-base.npz" --refits "%W%\output\facet_pairs\rounds\round1\metadata_pool" --config "%W%\output\facet_pairs\rounds\round1\model\config.json" --code "%W%\test\graph\facet_pairs" --out research\shard_check.json >> job.log 2>> job.err.log || (echo FAILED 5 >> job.log & exit /b 1)

echo === done %date% %time% >> job.log
echo done > job.finished
