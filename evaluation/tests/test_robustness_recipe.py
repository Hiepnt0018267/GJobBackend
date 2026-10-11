import math
from evaluation.run_ranking_robustness import fixtures,long_cv,PROTOCOL,flags,compare_vectors


def test_recipe_frozen_dimensions_and_identity_invariance():
    cvs,jobs=fixtures()
    assert cvs['REFERENCE_CV'].semantic_text==cvs['IDENTITY_VARIANT'].semantic_text
    assert len(cvs)==15 and len(jobs)==4
    assert PROTOCOL['max_embedding_requests']==22 and PROTOCOL['retry_count']==0
    assert PROTOCOL['num_batch']==4096 and PROTOCOL['truncate'] is False
    for n in (1,5,20):
        assert cvs[f'KEYWORD_STUFFED_{n}X'].semantic_text.count('Python')>n
    assert len(long_cv(350).experiences)<=100
    assert all(len(e.description)<=5000 for e in long_cv(350).experiences)


def test_flags_predefined_and_fixed_controls_rank_diagnostics():
    assert 'MATERIAL_SCORE_SHIFT' in flags(.05,0,'KEYWORD_STUFFED_20X')
    assert 'KEYWORD_STUFFING_SENSITIVITY' in flags(.06,0,'KEYWORD_STUFFED_20X')
    assert flags(.049,1,'KEYWORD_STUFFED_20X')==[]
    cvs={'REFERENCE_CV':[.6,.8],'TRANSFER_CONTROL':[.7,math.sqrt(1-.7**2)],
         'UNRELATED_CONTROL':[0.,1.],'KEYWORD_STUFFED_20X':[.9,math.sqrt(1-.9**2)]}
    rows,jds=compare_vectors(cvs,{'REFERENCE_JD':[1.,0.]})
    variant=next(r for r in rows if r['case_id']=='KEYWORD_STUFFED_20X')
    assert variant['reference_rank']==2 and variant['rank']==1
    assert variant['rank_delta']==-1 and math.isclose(variant['score_delta'],.3)
    assert jds[0]['ranks']==[2,1,3]
