from curious.review_verdict import parse_review_verdict

SUMMARY = """
Good work.

```review-verdict
OVERALL: FAIL
1_maintainability: PASS
2_correctness_performance: FAIL
3_spec_compliance: PASS
4_homogeneity: PASS
5_verification: FAIL
6_git_safety: PASS
blocking_issues:
- src/foo.ts:12 missing handler
evidence:
- npm test — 2 failed
next_develop:
- T2.1
```
"""


def test_parse_review_verdict():
    v = parse_review_verdict(SUMMARY)
    assert v is not None
    assert v.overall == "FAIL"
    assert v.criteria["2_correctness_performance"] == "FAIL"
    assert len(v.blocking_issues) == 1
    assert v.next_develop == "T2.1"
