"""Run with python -m evaluation.labeling_app; no production imports or routes."""
from __future__ import annotations

import argparse
import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, StrictStr
from starlette.middleware.trustedhost import TrustedHostMiddleware

from evaluation.common import EvaluationDataError
from evaluation.labeling_ai import LabelingAI
from evaluation.labeling_store import LabelingStore


class HumanDecision(BaseModel):
    label: StrictStr
    reason: StrictStr


def progress_for_input(input_path: Path) -> Path:
    """Each input dataset owns its progress; never fall back to legacy progress."""
    if input_path.stem == 'ranking_pairs_seed':
        return input_path.with_name('ranking_labeling_progress.csv')
    suffix = input_path.stem.removeprefix('evaluation_pairs_')
    return input_path.with_name(f'evaluation_labeling_progress_{suffix}.csv')


def output_for_input(input_path: Path) -> Path:
    if input_path.stem == 'ranking_pairs_seed':
        return input_path.with_name('ranking_pairs_labeled.csv')
    if input_path.stem == 'fresh_test_pairs_seed':
        return input_path.with_name('fresh_test_pairs_labeled.csv')
    return input_path.with_name('evaluation_pairs_labeled.csv')


def create_app(store: LabelingStore, ai: LabelingAI) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost', '127.0.0.1', '[::1]', 'testserver'])
    token = secrets.token_urlsafe(32)

    @app.middleware('http')
    async def protect_local(request: Request, call_next):
        if request.method == 'POST' and request.headers.get('x-review-token') != token:
            from fastapi.responses import JSONResponse
            return JSONResponse({'detail': 'Invalid local review session.'}, status_code=403)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; connect-src 'self'"
        return response

    @app.get('/', response_class=HTMLResponse)
    def home():
        template = 'ranking_ui.html' if getattr(store, 'is_ranking', False) else 'labeling_ui.html'
        return Path(__file__).with_name(template).read_text(encoding='utf-8').replace('__REVIEW_TOKEN__', token)

    @app.get('/review/state')
    def state():
        return {**store.summary(), 'model': ai.model if ai is not None else None}

    @app.get('/review/pairs/{pid}')
    def pair(pid: str):
        if pid not in store.by_id:
            raise HTTPException(404, 'Pair not found.')
        return store.pair(pid)

    @app.post('/review/pairs/{pid}/suggestion')
    def suggestion(pid: str):
        if ai is None:
            raise HTTPException(400, 'Ranking review is human-only; AI suggestions disabled.')
        if pid not in store.by_id:
            raise HTTPException(404, 'Pair not found.')
        try:
            pair_data = store.pair(pid)
            result = ai.suggest(pair_data['cv'], pair_data['job'])
            store.suggestion(pid, result.suggested_label, result.reason, ai.model)
            return store.state(pid)
        except (EvaluationDataError, OSError) as exc:
            raise HTTPException(503, str(exc)) from exc

    @app.post('/review/pairs/{pid}/decision')
    def decision(pid: str, body: HumanDecision):
        if pid not in store.by_id:
            raise HTTPException(404, 'Pair not found.')
        try:
            store.review(pid, body.label, body.reason)
            return store.summary()
        except (EvaluationDataError, OSError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post('/review/export')
    def export():
        try:
            return store.export()
        except (EvaluationDataError, OSError) as exc:
            raise HTTPException(400, str(exc)) from exc

    return app


def main(argv=None):
    parser = argparse.ArgumentParser(description='Local AI-assisted HUMAN labeling workspace.')
    parser.add_argument('--input', required=True, help='Authoritative pair dataset CSV.')
    parser.add_argument('--data-dir', required=True)
    parser.add_argument('--progress', help='Explicit progress file for this dataset; otherwise derived from --input.')
    parser.add_argument('--output', help='Labeled export; fresh seed defaults to fresh_test_pairs_labeled.csv.')
    parser.add_argument('--base-url', default='http://localhost:11434')
    parser.add_argument('--model', default='qwen3:8b')
    parser.add_argument('--port', type=int, default=8501)
    parser.add_argument('--ranking-manifest', default='evaluation/results/ranking-dataset/seed_manifest.json')
    args = parser.parse_args(argv)
    try:
        input_path = Path(args.input)
        progress = Path(args.progress) if args.progress else progress_for_input(input_path)
        output = Path(args.output) if args.output else output_for_input(input_path)
        if input_path.stem == 'ranking_pairs_seed':
            from evaluation.ranking_labeling import RankingLabelingStore
            store = RankingLabelingStore(input_path, Path(args.data_dir), progress, output, Path(args.ranking_manifest))
        elif input_path.stem == 'fresh_test_pairs_seed':
            from evaluation.fresh_labeling import FreshLabelingStore
            store = FreshLabelingStore(input_path, Path(args.data_dir), progress, output)
        else:
            store = LabelingStore(input_path, Path(args.data_dir), progress, output)
        rubric = Path(__file__).with_name('LABELING_GUIDE.md').read_text(encoding='utf-8')
        ai = None if getattr(store, 'is_ranking', False) else LabelingAI(args.base_url, args.model, rubric)
    except (EvaluationDataError, OSError) as exc:
        parser.error(str(exc))
    import uvicorn
    counts = store.summary()
    print(f'Input: {input_path.resolve()}\nProgress: {progress.resolve()}')
    print(f'Open http://127.0.0.1:{args.port} — Reviewed: {counts["reviewed"]} / {counts["total"]}; Remaining: {counts["remaining"]}.')
    uvicorn.run(create_app(store, ai), host='127.0.0.1', port=args.port, access_log=False)


if __name__ == '__main__':
    main()
