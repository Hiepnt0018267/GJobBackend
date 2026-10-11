"""Explicit grouped result contract: synthetic only, no provider or database."""
from types import SimpleNamespace as NS
from uuid import UUID

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from test_applicant_ranking import applicants, service, listing


def test_all_keeps_full_ranked_and_unranked_groups(tmp_path, monkeypatch):
    rows = applicants(7)
    s = service(tmp_path, rows, {i: i / 10 for i in range(1, 6)}, monkeypatch)
    before = [a.status for a in rows]
    result = listing(s, rows, ranking_mode="all")
    assert result.ranked_available_count == result.returned_ranked_count == 5
    assert result.unranked_count == 2 and result.total == 7
    assert [i.cv_id.int for i in result.items[:5]] == [5, 4, 3, 2, 1]
    assert all(i.ai_rank is None for i in result.items[5:])
    assert [a.status for a in rows] == before


def test_top_n_ranks_whole_pool_then_limits_only_ranked_before_pagination(tmp_path, monkeypatch):
    rows = applicants(23)
    signals = {i: i / 25 for i in range(1, 21)}
    s = service(tmp_path, rows, signals, monkeypatch)
    first = listing(s, rows, ranking_mode="top_n", top_n=10, page_size=5)
    assert first.ranked_available_count == 20 and first.returned_ranked_count == 10
    assert first.unranked_count == 3 and first.total == 13 and first.total_pages == 3
    assert [i.cv_id.int for i in first.items] == [20, 19, 18, 17, 16]
    assert s.cache.lookups == 24  # every unique CV plus JD, not first N DB rows
    lookups = s.cache.lookups
    s.cache.signals[22] = .99
    all_items = list(first.items)
    for page in (2, 3):
        all_items += listing(s, rows, ranking_mode="top_n", top_n=10,
            page_size=5, page=page, snapshot=first.ranking_snapshot).items
    assert s.cache.lookups == lookups
    assert [i.cv_id.int for i in all_items[:10]] == list(range(20, 10, -1))
    assert [i.cv_id.int for i in all_items[10:]] == [21, 22, 23]
    assert len({i.id for i in all_items}) == 13
    assert all(i.ai_rank is None and i.semantic_match_score is None for i in all_items[10:])


def test_fewer_ranked_than_n_never_pads_with_missing_states(tmp_path, monkeypatch):
    rows = applicants(10)
    signals = {i: i / 10 for i in range(1, 7)}
    signals.update({7: "pending", 8: "unavailable", 9: "error", 10: "pending"})
    s = service(tmp_path, rows, signals, monkeypatch)
    result = listing(s, rows, ranking_mode="top_n", top_n=10)
    assert result.returned_ranked_count == 6 and result.unranked_count == 4
    assert result.total == 10
    assert [i.ai_rank for i in result.items[:6]] == list(range(1, 7))
    assert [i.ranking_status for i in result.items[6:]] == ["pending", "unavailable", "error", "pending"]
    assert all(i.ai_rank is None for i in result.items[6:])


def test_zero_ranked_retains_every_unranked_and_mode_changes_snapshot(tmp_path, monkeypatch):
    rows = applicants(4)
    s = service(tmp_path, rows, {}, monkeypatch)
    first = listing(s, rows, ranking_mode="top_n", top_n=10)
    assert first.total == 4 and first.returned_ranked_count == 0 and first.unranked_count == 4
    for options in ({"ranking_mode": "top_n", "top_n": 5}, {"ranking_mode": "all"}):
        with pytest.raises(HTTPException) as exc:
            listing(s, rows, snapshot=first.ranking_snapshot, **options)
        assert exc.value.status_code == 409
        fresh = listing(s, rows, **options)
        assert fresh.ranking_snapshot != first.ranking_snapshot


@pytest.mark.parametrize("options", [
    {"ranking_mode": "top_n"}, {"ranking_mode": "top_n", "top_n": 0},
    {"ranking_mode": "top_n", "top_n": -2}, {"ranking_mode": "top_n", "top_n": 1.5},
    {"ranking_mode": "top_n", "top_n": True}, {"ranking_mode": "all", "top_n": 10},
    {"ranking_mode": "unknown"},
])
def test_invalid_domain_options_do_no_ai_work(tmp_path, monkeypatch, options):
    rows = applicants(1)
    s = service(tmp_path, rows, {}, monkeypatch)
    monkeypatch.setattr(s.inputs, "build_cv_inputs", lambda *a: pytest.fail("Invalid request did AI work"))
    with pytest.raises(HTTPException) as exc:
        listing(s, rows, **options)
    assert exc.value.status_code == 422 and s.cache.lookups == 0


def test_public_endpoint_contract_and_validation_without_db(tmp_path, monkeypatch):
    from app.routers import recruiter_applications as routes
    from app.core.database import get_db
    from app.services.recruiter_application_service import RecruiterApplicationService
    from app.services import applicant_ranking_service as ranking
    rows = applicants(3)
    s = service(tmp_path, rows, {1: .5, 3: .9}, monkeypatch)
    monkeypatch.setattr(ranking, "ApplicantRankingService", lambda db: s)
    actual = RecruiterApplicationService.__new__(RecruiterApplicationService)
    actual.db = None
    calls = []
    class Repo:
        def get_owned_job(self, job_id, owner): return rows[0].job if job_id == rows[0].job_id else None
        def list_owned_applications(self, *args): calls.append(args); return rows, len(rows)
    actual.repository = Repo()
    monkeypatch.setattr(routes, "RecruiterApplicationService", lambda db: actual)
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: None
    for route in routes.router.routes:
        if hasattr(route, "dependant"):
            for dep in route.dependant.dependencies:
                if dep.name == "current_user": app.dependency_overrides[dep.call] = lambda: NS(id=UUID(int=9))
    with TestClient(app) as client:
        path = f"/api/v1/recruiters/jobs/{rows[0].job_id}/applications"
        for query in ("ranking_mode=top_n", "ranking_mode=top_n&top_n=0", "ranking_mode=top_n&top_n=-1",
                      "ranking_mode=top_n&top_n=1.5", "ranking_mode=all&top_n=2", "ranking_mode=unknown"):
            assert client.get(path + "?sort=ai_match&" + query).status_code == 422
        assert calls == [] and s.cache.lookups == 0
        response = client.get(path + "?sort=ai_match&ranking_mode=top_n&top_n=1")
        assert response.status_code == 200
        body = response.json()
        assert body["ranking_mode"] == "top_n" and body["requested_top_n"] == 1
        assert body["ranked_available_count"] == 2 and body["returned_ranked_count"] == 1
        assert body["unranked_count"] == 1 and body["total"] == 2
        assert body["items"][0]["cv_id"] == str(rows[2].cv_id)
        assert body["items"][1]["ranking_status"] == "pending"
        assert client.get(path + "?ranking_mode=all").status_code == 422
