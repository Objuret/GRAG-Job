"""Run the experimental fixed-program arm through the unchanged real harness."""
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'prod'))
sys.path.insert(0,str(ROOT/'test'))
import run as runner

if __name__=='__main__':
    runner.ARMS=(*runner.ARMS,'artefact_facet_program')
    runner.CHAR_BUDGET_ARMS=(*runner.CHAR_BUDGET_ARMS,'artefact_facet_program')
    runner.main()
