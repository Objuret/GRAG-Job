"""Standard harness entry point for the metadata-serializable program adapter."""
from facet_program_runner import runner

if __name__=='__main__':
    runner.ARMS=(*runner.ARMS,'artefact_facet_program_v2')
    runner.CHAR_BUDGET_ARMS=(*runner.CHAR_BUDGET_ARMS,'artefact_facet_program_v2')
    runner.main()
