"""Register only the two fixed experimental leaders in the existing harness."""
from facet_program_runner import runner

if __name__=='__main__':
    additions=('artefact_facet_leader_hits','artefact_facet_leader_macro')
    runner.ARMS=(*runner.ARMS,*additions)
    runner.CHAR_BUDGET_ARMS=(*runner.CHAR_BUDGET_ARMS,*additions)
    runner.main()
