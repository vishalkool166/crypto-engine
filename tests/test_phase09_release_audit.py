"""Release audit must never convert local success into production certification."""
from scripts import release_audit


def test_audit_detects_runtime_payloads_and_duplicate_ledgers(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    assert release_audit.inspect_tree(repo)['status'] == 'PASS'
    (repo / 'database').mkdir()
    (repo / 'database' / 'private.db').write_text('private')
    (repo / '.github' / 'workflows').mkdir(parents=True)
    result = release_audit.inspect_tree(repo)
    assert result['status'] == 'FAIL'
    assert 'private.db' in str(result['detail'])
    assert 'GitHub Actions' in str(result['detail'])


def test_cannot_certify_live_from_local_tests():
    report = release_audit.evaluate(run_tests=False)
    assert report['release_certified'] is False
    assert report['paper_trading_only'] is True
    assert len(report['external_gates']) >= 5
    assert report['external_gates']['frontend_clean_install_lint_typecheck_build'].startswith('PASS locally')
    assert all(v.startswith(('BLOCKED:', 'PASS locally')) for v in report['external_gates'].values())
    assert any('Cloudflare Pages deployment checks still required' in v
               for v in report['external_gates'].values())


def test_paper_release_gate_rejects_live_or_unknown_modes():
    assert release_audit.paper_mode_gate('paper')['status'] == 'PASS'
    assert release_audit.paper_mode_gate('live')['status'] == 'FAIL'
    assert release_audit.paper_mode_gate('unknown')['status'] == 'FAIL'
