"""Fresh-cache live adapter for the sealed record-assembly comparisons."""
from facet_record_assembly_lab import execute_record


def execute(lab,case,program):
    if program.get('record_assembly',{}).get('mode')=='contiguous' and program.get('tie_break','id')!='id':
        raise ValueError('Contiguous record assembly with an extra nomination tie rule is not implemented')
    # An edited live graph can change routes between requests. Batch gate caches
    # belong to the fixed catalog; do not carry them across live graph edits.
    result=execute_record(lab,{**case,'cache':{},'record_gate_cache':{}},program)
    if next(n for n in program['nodes'] if n['id']==program['output'])['op']=='record_component_assembly':
        result['assembly_components']=lab.components
        result['assembly_id_order']=lab.id_order
    summary=result['stages'].pop('record_tag_frontier',None)
    if summary is not None:result['record_frontier_inspection']=summary
    return result
