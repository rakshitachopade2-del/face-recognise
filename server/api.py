from __future__ import annotations

import json
from typing import Annotated

from fastapi import FastAPI, File, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from server.config import Settings
from server.media import MediaError, safe_path
from server.providers import ProviderError
from server.reporting import report
from server.service import DomainError, Service, event_access, uid


class EventInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    authorization: str = Field(min_length=1, max_length=1000)
    days: int = Field(default=30, ge=1, le=30)


class ConsentInput(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    basis: str = Field(min_length=1, max_length=1000)
    days: int = Field(default=30, ge=1, le=30)


def create_app(settings=None, service=None):
    settings = settings or Settings.environment()
    s = service or Service(settings)
    app = FastAPI(title="Face POC — local operator simulator", version="0.1.0")
    app.state.service = s
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.origins), allow_credentials=True,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-Local-Request"])
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]"])

    @app.middleware("http")
    async def local_boundary(request, call_next):
        origin = request.headers.get("origin")
        if request.client and request.client.host not in {"127.0.0.1", "::1", "testclient"}:
            return JSONResponse({"detail": "loopback_clients_only"}, status_code=403)
        if origin and origin not in settings.origins:
            return JSONResponse({"detail": "origin_not_allowed"}, status_code=403)
        if (request.method not in {"GET", "HEAD", "OPTIONS"} and not origin
                and request.headers.get("x-local-request") != "1"):
            return JSONResponse({"detail": "origin_or_explicit_local_cli_header_required"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store, private"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=exc.status)

    @app.exception_handler(MediaError)
    @app.exception_handler(ProviderError)
    async def input_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    def operator(request):
        s.authorize(request.cookies.get("operator_session", ""), "operator")

    def guest(request, event_id, participant_id):
        s.authorize(request.cookies.get("guest_session", ""), "guest", event_id, participant_id)

    @app.get("/api/health")
    def health():
        return {"status": "local-only", "synthetic": s.provider.synthetic, "provider": s.op.provider,
                "configuration_state": s.op.state, "enrollment_count": s.op.enrollment_count,
                "notice": "Operator identity simulator. No authentication or liveness verification."}

    @app.post("/api/session")
    def start_operator(response: Response):
        response.set_cookie("operator_session", s.session("operator"), httponly=True,
                            samesite="strict", max_age=3600, path="/api")
        return {"role": "operator", "warning": "Local simulator only; this is not authentication."}

    @app.get("/api/events")
    def events(request: Request):
        operator(request)
        with s.db.connect() as db:
            return [dict(r) for r in db.execute("SELECT id,name,authorized,expires FROM events ORDER BY created DESC")]

    @app.post("/api/events")
    def event_create(body: EventInput, request: Request):
        operator(request)
        return {"id": s.create_event(body.name, body.authorization, body.days)}

    @app.post("/api/events/{event_id}/photos")
    def upload(event_id: str, request: Request, files: Annotated[list[UploadFile], File()]):
        operator(request)
        if len(files) > 100:
            raise DomainError("maximum_100_files_per_batch")
        batch = uid()
        return {"batch_id": batch, "files": [s.import_one(event_id, f.file.read(settings.max_bytes + 1), batch, i)
                                             for i, f in enumerate(files)]}

    @app.get("/api/events/{event_id}/status")
    def status(event_id: str, request: Request):
        operator(request)
        with s.db.connect() as db:
            event_access(db, event_id)
            return {
                "photos": [dict(r) for r in db.execute("SELECT id,state,width,height FROM photos WHERE event_id=?", (event_id,))],
                "jobs": [dict(r) for r in db.execute("""SELECT id,photo_id,kind,status,attempts,error,lease_expiry,
                          heartbeat FROM jobs WHERE event_id=? ORDER BY created DESC""", (event_id,))],
                "imports": [dict(r) for r in db.execute("SELECT ordinal,state,reason FROM imports WHERE event_id=? ORDER BY created DESC LIMIT 100", (event_id,))],
                "participants": [dict(r) for r in db.execute("""SELECT p.id,p.label,p.active,
                    EXISTS(SELECT 1 FROM enrollments e WHERE e.participant_id=p.id AND e.namespace=?) AS enrolled
                    FROM participants p WHERE p.event_id=?""", (s.namespace, event_id))],
            }

    @app.post("/api/events/{event_id}/jobs/{job_id}/retry")
    def retry(event_id: str, job_id: str, request: Request):
        operator(request)
        s.retry(event_id, job_id)
        return {"state": "pending"}

    @app.post("/api/events/{event_id}/participants")
    def consent(event_id: str, body: ConsentInput, request: Request):
        operator(request)
        return s.consent(event_id, body.label, body.basis, body.days)

    @app.post("/api/events/{event_id}/participants/{participant_id}/enrollment")
    def enroll(event_id: str, participant_id: str, request: Request, files: Annotated[list[UploadFile], File()]):
        operator(request)
        return s.enroll(event_id, participant_id, [f.file.read(settings.max_bytes + 1) for f in files])

    @app.post("/api/events/{event_id}/participants/{participant_id}/preview")
    def preview(event_id: str, participant_id: str, request: Request, response: Response):
        operator(request)
        response.set_cookie("guest_session", s.session("guest", event_id, participant_id), httponly=True,
                            samesite="strict", max_age=3600, path="/api")
        return {"state": "guest_simulator", "candidate_previews": False}

    @app.post("/api/events/{event_id}/participants/{participant_id}/withdraw")
    def withdraw(event_id: str, participant_id: str, request: Request, response: Response):
        operator(request)
        s.withdraw(event_id, participant_id)
        response.delete_cookie("guest_session", path="/api")
        return {"state": "withdrawn", "enrollment_deleted": True}

    @app.get("/api/events/{event_id}/participants/{participant_id}/gallery")
    def gallery(event_id: str, participant_id: str, request: Request):
        guest(request, event_id, participant_id)
        return s.gallery(event_id, participant_id)

    @app.post("/api/events/{event_id}/participants/{participant_id}/gallery/{photo_id}/reject")
    def reject(event_id: str, participant_id: str, photo_id: str, request: Request):
        guest(request, event_id, participant_id)
        s.reject(event_id, participant_id, photo_id)
        return {"state": "suppressed"}

    @app.get("/api/events/{event_id}/participants/{participant_id}/gallery/{photo_id}/media")
    def gallery_media(event_id: str, participant_id: str, photo_id: str, request: Request):
        guest(request, event_id, participant_id)
        if not any(p["id"] == photo_id for p in s.gallery(event_id, participant_id)):
            raise DomainError("released_photo_required", 403)
        with s.db.connect() as db:
            row = db.execute("SELECT derivative_key FROM photos WHERE id=? AND event_id=?", (photo_id, event_id)).fetchone()
        content = safe_path(settings.data_dir, row[0]).read_bytes()
        # IO can outlast consent. Reauthorize after reading, immediately before handing bytes to HTTP.
        guest(request, event_id, participant_id)
        if not any(p["id"] == photo_id for p in s.gallery(event_id, participant_id)):
            raise DomainError("released_photo_required", 403)
        return Response(content, media_type="image/png")

    @app.get("/api/events/{event_id}/diagnostics")
    def diagnostics(event_id: str, request: Request):
        operator(request)
        with s.db.connect() as db:
            event_access(db, event_id)
            faces = [dict(r) for r in db.execute("SELECT id,photo_id,bbox,quality,status FROM faces WHERE event_id=? AND namespace=?",
                                                (event_id, s.namespace))]
            for face in faces:
                face["bbox"], face["quality"] = json.loads(face["bbox"]), json.loads(face["quality"])
            matches = [dict(r) for r in db.execute("SELECT photo_id,face_id,participant_id,score,margin,decision,reason FROM proposed_matches WHERE event_id=? AND config_id=?",
                                                  (event_id, s.config_id))]
            return {"faces": faces, "proposals": matches, "access": "operator_only"}

    @app.get("/api/events/{event_id}/photos/{photo_id}/operator-media")
    def operator_media(event_id: str, photo_id: str, request: Request):
        operator(request)
        with s.db.connect() as db:
            event_access(db, event_id)
            row = db.execute("SELECT derivative_key FROM photos WHERE event_id=? AND id=?", (event_id, photo_id)).fetchone()
        if not row:
            raise DomainError("photo_not_found", 404)
        content = safe_path(settings.data_dir, row[0]).read_bytes()
        with s.db.connect() as db:
            event_access(db, event_id)
        return Response(content, media_type="image/png")

    @app.post("/api/events/{event_id}/report")
    def experiment_report(event_id: str, request: Request):
        operator(request)
        with s.db.connect() as db:
            event_access(db, event_id)
        return report(s, event_id)

    return app
