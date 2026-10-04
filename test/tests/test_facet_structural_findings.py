from facet_structural_findings import summarize


def test_only_one_structural_change_is_matched_and_context_reversal_is_visible():
    programs=[]; rows=[]
    for reduction,gate,hits in [('before_graph','off',1),('after_graph','off',3),
                                ('before_graph','each_step',4),('after_graph','each_step',2)]:
        pid=str(len(programs))
        programs.append(dict(id=pid,factors={},ordering=dict(reduction=reduction,description_gate=gate)))
        rows.append(dict(program_id=pid,hits=hits,recall_id=hits/5,order_sha256=pid))
    result=summarize(programs,{'case_001':rows})
    assert len(result['matched_effects'])==4
    assert all((e['left'],e['right']) not in [('0','3'),('1','2')] for e in result['matched_effects'])
    reversal=next(x for x in result['conditional_sign_reversals'] if x['factor']=='reduction')
    assert reversal['negative_context']['gold_hits_delta']==-2
    assert reversal['positive_context']['gold_hits_delta']==2
    assert result['leaders'][0]['program_id']=='2'
    assert len(result['matched_four_corner_reversals'])==1
    assert abs(result['matched_four_corner_reversals'][0]['difference_in_hit_deltas'])==4
