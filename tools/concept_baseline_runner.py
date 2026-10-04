"""Register the isolated concept baseline with the unchanged standard harness."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'prod'),str(ROOT/'test')]
import run as runner

if __name__=='__main__':
    runner.ARMS=(*runner.ARMS,'artefact_concept_baseline')
    runner.CHAR_BUDGET_ARMS=(*runner.CHAR_BUDGET_ARMS,'artefact_concept_baseline')
    runner.main()
