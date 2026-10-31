from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from app import pipeline
from app.ids import new_id
from app.schemas import ApproveRequest, IngestRequest, VoiceEditRequest
from app.services import clock, runs

router = APIRouter(tags=["runs"])


def _not_found(thread_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"run {thread_id} not found")


@router.post("/ingest")
async def ingest(body: IngestRequest) -> dict:
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="text is empty")
    if not body.project.strip():
        raise HTTPException(status_code=422, detail="project is empty")
    try:
        meeting_date = clock.parse(body.date).date().isoformat()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    thread_id = new_id("run")
    meeting = {
        "id": new_id("mtg"),
        "project": body.project.strip(),
        "title": body.title.strip() or "Untitled meeting",
        "date": meeting_date,
        "speaker": body.speaker.strip(),
        "source_type": body.source_type,
    }
    initial_state = {
        "thread_id": thread_id,
        "meeting": meeting,
        "raw_text": body.text,
        "clean_text": body.text,  # the normalizer replaces this; stubs pass it through
        "corrections": [], "decisions": [], "tasks": [], "conflicts": [],
        "questions": [], "ripples": [], "heads_up": [], "related": {}, "result": {},
    }
    pipeline.start(thread_id, meeting["project"], initial_state)
    return {"thread_id": thread_id}


@router.get("/runs/{thread_id}/stream")
async def stream(thread_id: str):
    try:
        await pipeline.ensure_channel(thread_id)
    except KeyError:
        raise _not_found(thread_id) from None

    async def events():
        async for e in runs.subscribe(thread_id):
            yield {"event": e.type, "data": e.model_dump_json()}

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
