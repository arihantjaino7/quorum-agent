from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sse_starlette.sse import EventSourceResponse

from app import pipeline
from app.ids import new_id
from app.schemas import ApproveRequest, IngestRequest, VoiceEditRequest
from app.services import clock, ingest_parsing, runs

router = APIRouter(tags=["runs"])


def _not_found(thread_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"run {thread_id} not found")


def _start(project: str, title: str, date: str, speaker: str, source_type: str, text: str) -> dict:
    if not text.strip():
        raise HTTPException(status_code=422, detail="text is empty")
    if not project.strip():
        raise HTTPException(status_code=422, detail="project is empty")
    try:
        meeting_date = clock.parse(date).date().isoformat()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    thread_id = new_id("run")
    meeting = {
        "id": new_id("mtg"),
        "project": project.strip(),
        "title": title.strip() or "Untitled meeting",
        "date": meeting_date,
        "speaker": speaker.strip(),
        "source_type": source_type,
    }
    initial_state = {
        "thread_id": thread_id,
        "meeting": meeting,
        "raw_text": text,
        "clean_text": text,  # the normalizer replaces this; stubs pass it through
        "corrections": [], "decisions": [], "tasks": [], "conflicts": [],
        "questions": [], "ripples": [], "heads_up": [], "related": {}, "result": {},
    }
    pipeline.start(thread_id, meeting["project"], initial_state)
    return {"thread_id": thread_id}


@router.post("/ingest")
async def ingest(body: IngestRequest) -> dict:
    return _start(body.project, body.title, body.date, body.speaker, body.source_type, body.text)


AUDIO_TYPES = (".mp3", ".m4a", ".wav", ".webm")


async def _transcribe(name: str, data: bytes) -> str:
    """Speech to text with Groq Whisper (the key may be injected by the network proxy)."""
    import httpx

    from app.config import get_settings
    from app.integrations import llm

    if not llm.available():
        raise HTTPException(status_code=422, detail="Audio needs Groq: set GROQ_API_KEY, or paste the transcript instead.")
    s = get_settings()
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post("https://api.groq.com/openai/v1/audio/transcriptions",
                                  headers={"Authorization": f"Bearer {s.groq_api_key or llm.PROXY_PLACEHOLDER_KEY}"},
                                  data={"model": s.groq_model_whisper, "response_format": "json"},
                                  files={"file": (name, data)})
        r.raise_for_status()
        return r.json()["text"]
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Transcription failed ({type(e).__name__}). Try again or paste the text.") from e


@router.post("/ingest/file")
async def ingest_file(file: UploadFile = File(...), project: str = Form(...), title: str = Form(""), date: str = Form(...),
                      speaker: str = Form(...), source_type: str = Form("transcript")) -> dict:
    name, data = file.filename or "upload", await file.read()
    if name.lower().endswith(AUDIO_TYPES):
        return _start(project, title, date, speaker, "audio", await _transcribe(name, data))
    try:
        parsed = ingest_parsing.parse_file(name, data)
    except ingest_parsing.UnsupportedFormat as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return _start(project, title, date, speaker, "transcript", parsed.text)


@router.get("/runs/{thread_id}/stream")
async def stream(thread_id: str, until: str | None = None):
    """SSE trace. Stays open through execution by default; ``?until=review`` ends it at review_ready
    (used by tests, whose in-process client cannot read a stream that stays open)."""
    try:
        await pipeline.ensure_channel(thread_id)
    except KeyError:
        raise _not_found(thread_id) from None

    async def events():
        async for e in runs.subscribe(thread_id):
            yield {"event": e.type, "data": e.model_dump_json()}
            if until == "review" and e.type in ("review_ready", "error"):
                return

    return EventSourceResponse(events(), ping=15)


@router.get("/runs/{thread_id}/review")
async def get_review(thread_id: str):
    try:
        return (await pipeline.get_review(thread_id)).model_dump()
    except KeyError:
        raise _not_found(thread_id) from None
    except pipeline.RunConflict as e:
        raise HTTPException(status_code=409, detail=str(e)) from None


@router.post("/runs/{thread_id}/approve")
async def approve(thread_id: str, body: ApproveRequest) -> dict:
    try:
        return await pipeline.approve(thread_id, body.resolutions, body.ripple_actions)
    except KeyError:
        raise _not_found(thread_id) from None
    except pipeline.RunConflict as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from None


@router.post("/runs/{thread_id}/voice-edit")
async def voice_edit(thread_id: str, body: VoiceEditRequest) -> dict:
    if not body.instruction.strip():
        raise HTTPException(status_code=422, detail="instruction is empty")
    try:
        review, changes = await pipeline.edit(thread_id, body.instruction.strip())
    except KeyError:
        raise _not_found(thread_id) from None
    except pipeline.RunConflict as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from None
    return {"review": review.model_dump(), "changes": changes}


@router.post("/runs/{thread_id}/reject")
async def reject(thread_id: str) -> dict:
    try:
        await pipeline.reject(thread_id)
    except KeyError:
        raise _not_found(thread_id) from None
    except pipeline.RunConflict as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    return {"ok": True}


@router.post("/runs/{thread_id}/retry")
async def retry(thread_id: str) -> dict:
    try:
        await pipeline.retry(thread_id)
    except KeyError:
        raise _not_found(thread_id) from None
    except pipeline.RunConflict as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    return {"ok": True}
