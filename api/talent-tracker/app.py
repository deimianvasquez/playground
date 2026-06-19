
import json
import os
from uuid import uuid4
from datetime import datetime
from typing import Optional
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi import FastAPI, HTTPException, Query, Path, Body, status as http_status
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError, BaseModel, constr
from .models import RecordCreate, RecordOut, NoteCreate, NoteOut
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded


app = FastAPI(
	title="Talent Tracker API",
	description='API para gestión de talento. <a href="/" target="_self">⬅ Volver al Home</a>',
	version="1.0.0",
	docs_url=None,
	openapi_tags=[
		{
			"name": "Records",
			"description": "Operations on Talent Records.",
		},
		{
			"name": "Notes",
			"description": "Operations on Notes for a Record.",
		}
	]
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Endpoint personalizado para Swagger UI con favicon global
@app.get("/docs", include_in_schema=False)
async def swagger_ui_html():
	return get_swagger_ui_html(
		title="4Geeks Playground - Talent Tracker API",
		openapi_url="/tracker/api/v1/openapi.json",
		swagger_favicon_url="/favicon.ico",
		# swagger_css_url="/static/swagger-ui.css",
	)


@app.get("/records", tags=["Records"])
def get_records(
	status: str = Query(None, description="Filter by status: received, in_progress, selected, discarded"),
	stage: str = Query(None, description="Filter by stage: pending, review, personal_interview, technical_interview, offer_presented"),
	search: str = Query(None, description="Search in full_name or email"),
	page: int = Query(1, ge=1, description="Page number, default 1"),
	limit: int = Query(20, ge=1, description="Results per page, default 20 (no max limit)")
):
	data_path = os.path.join(os.path.dirname(__file__), "data", "mock_data.json")
	try:
		with open(data_path, "r", encoding="utf-8") as f:
			data = json.load(f)
		records = data.get("records", [])

		# Filtros
		if status:
			records = [r for r in records if r.get("status") == status]
		if stage:
			records = [r for r in records if r.get("stage") == stage]
		if search:
			search_lower = search.lower()
			records = [r for r in records if search_lower in r.get("full_name", "").lower() or search_lower in r.get("email", "").lower()]

		# Paginación
		total = len(records)
		start = (page - 1) * limit
		end = start + limit
		paginated = records[start:end]

		return {
			"total": total,
			"page": page,
			"limit": limit,
			"data": paginated
		}
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error leyendo mock_data.json: {e}")
	

# Endpoint para obtener el detalle de un registro por id
@app.get("/records/{id}", tags=["Records"])
def get_record_by_id(id: str = Path(..., description="ID del registro")):
	data_path = os.path.join(os.path.dirname(__file__), "data", "mock_data.json")
	try:
		with open(data_path, "r", encoding="utf-8") as f:
			data = json.load(f)
		records = data.get("records", [])
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error leyendo mock_data.json: {e}")

	for record in records:
		if record.get("id") == id:
			# Solo los campos principales
			return {
				"id": record.get("id"),
				"full_name": record.get("full_name"),
				"email": record.get("email"),
				"phone": record.get("phone"),
				"position": record.get("position"),
				"linkedin_url": record.get("linkedin_url"),
				"cv_url": record.get("cv_url"),
				"status": record.get("status"),
				"stage": record.get("stage"),
				"experience_years": record.get("experience_years"),
				"notes_count": record.get("notes_count"),
				"applied_at": record.get("applied_at"),
				"updated_at": record.get("updated_at")
			}
	return JSONResponse(status_code=404, content={"error": "Record not found"})

  
@app.post("/records", status_code=201, response_model=RecordOut, tags=["Records"])
def create_record(record: RecordCreate = Body(...)):
	data_path = os.path.join(os.path.dirname(__file__), "data", "mock_data.json")
	try:
		with open(data_path, "r", encoding="utf-8") as f:
			data = json.load(f)
		records = data.get("records", [])
	except Exception as e:
		return JSONResponse(status_code=500, content={"error": f"Error leyendo mock_data.json: {e}"})

	# Validación extra (por si acaso)
	try:
		record_data = record.dict()
	except ValidationError as ve:
		return JSONResponse(status_code=422, content={
			"error": "Validation error",
			"details": ve.errors()
		})

	# Crear nuevo registro
	now = datetime.utcnow().isoformat() + "Z"
	new_record = {
		"id": str(uuid4()),
		"full_name": record_data["full_name"],
		"email": record_data["email"],
		"phone": record_data["phone"],
		"position": record_data["position"],
		"linkedin_url": record_data.get("linkedin_url"),
		"cv_url": record_data.get("cv_url"),
		"status": "received",
		"stage": "pending",
		"experience_years": record_data["experience_years"],
		"notes_count": 0,
		"applied_at": now,
		"updated_at": now
	}
	records.append(new_record)
	data["records"] = records
	try:
		with open(data_path, "w", encoding="utf-8") as f:
			json.dump(data, f, ensure_ascii=False, indent=2)
	except Exception as e:
		return JSONResponse(status_code=500, content={"error": f"Error guardando mock_data.json: {e}"})

	return new_record


# PUT /records/{id} - reemplaza datos editables
@app.put("/records/{id}", response_model=RecordOut, tags=["Records"])
def replace_record(
	id: str = Path(..., description="ID del registro"),
	record: RecordCreate = Body(...)
):
	data_path = os.path.join(os.path.dirname(__file__), "data", "mock_data.json")
	try:
		with open(data_path, "r", encoding="utf-8") as f:
			data = json.load(f)
		records = data.get("records", [])
	except Exception as e:
		return JSONResponse(status_code=500, content={"error": f"Error leyendo mock_data.json: {e}"})

	for idx, rec in enumerate(records):
		if rec.get("id") == id:
			# Solo reemplaza campos editables, no status ni stage
			now = datetime.utcnow().isoformat() + "Z"
			updated = {
				**rec,
				"full_name": record.full_name,
				"email": record.email,
				"phone": record.phone,
				"position": record.position,
				"linkedin_url": record.linkedin_url,
				"cv_url": record.cv_url,
				"experience_years": record.experience_years,
				"updated_at": now
			}
			records[idx] = updated
			data["records"] = records
			try:
				with open(data_path, "w", encoding="utf-8") as f:
					json.dump(data, f, ensure_ascii=False, indent=2)
			except Exception as e:
				return JSONResponse(status_code=500, content={"error": f"Error guardando mock_data.json: {e}"})
			return updated
	return JSONResponse(status_code=404, content={"error": "Record not found"})


# PATCH /records/{id} - modifica status o stage
class RecordPatch(BaseModel):
	status: Optional[str] = None
	stage: Optional[str] = None


valid_status = {"received", "in_progress", "selected", "discarded"}
valid_stage = {"pending", "review", "personal_interview", "technical_interview", "offer_presented"}


@app.patch("/records/{id}", response_model=RecordOut, tags=["Records"])
def patch_record(
	id: str = Path(..., description="ID del registro"),
	patch: RecordPatch = Body(...)
):
	if patch.status is None and patch.stage is None:
		return JSONResponse(status_code=400, content={"error": "At least one field (status or stage) is required"})
	errors = {}
	if patch.status is not None and patch.status not in valid_status:
		errors["status"] = f"Must be one of: {', '.join(valid_status)}"
	if patch.stage is not None and patch.stage not in valid_stage:
		errors["stage"] = f"Must be one of: {', '.join(valid_stage)}"
	if errors:
		return JSONResponse(status_code=422, content={"error": "Invalid value", "details": errors})

	data_path = os.path.join(os.path.dirname(__file__), "data", "mock_data.json")
	try:
		with open(data_path, "r", encoding="utf-8") as f:
			data = json.load(f)
		records = data.get("records", [])
	except Exception as e:
		return JSONResponse(status_code=500, content={"error": f"Error leyendo mock_data.json: {e}"})

	for idx, rec in enumerate(records):
		if rec.get("id") == id:
			now = datetime.utcnow().isoformat() + "Z"
			updated = {**rec}
			if patch.status is not None:
				updated["status"] = patch.status
			if patch.stage is not None:
				updated["stage"] = patch.stage
			updated["updated_at"] = now
			records[idx] = updated
			data["records"] = records
			try:
				with open(data_path, "w", encoding="utf-8") as f:
					json.dump(data, f, ensure_ascii=False, indent=2)
			except Exception as e:
				return JSONResponse(status_code=500, content={"error": f"Error guardando mock_data.json: {e}"})
			return updated
	return JSONResponse(status_code=404, content={"error": "Record not found"})


# DELETE /records/{id}
@app.delete("/records/{id}", status_code=204, tags=["Records"])
def delete_record(id: str = Path(..., description="ID del registro")):
	data_path = os.path.join(os.path.dirname(__file__), "data", "mock_data.json")
	try:
		with open(data_path, "r", encoding="utf-8") as f:
			data = json.load(f)
		records = data.get("records", [])
	except Exception as e:
		return JSONResponse(status_code=500, content={"error": f"Error leyendo mock_data.json: {e}"})

	for idx, rec in enumerate(records):
		if rec.get("id") == id:
			del records[idx]
			data["records"] = records
			try:
				with open(data_path, "w", encoding="utf-8") as f:
					json.dump(data, f, ensure_ascii=False, indent=2)
			except Exception as e:
				return JSONResponse(status_code=500, content={"error": f"Error guardando mock_data.json: {e}"})
			return Response(status_code=204)
	return JSONResponse(status_code=404, content={"error": "Record not found"})


# GET /records/{id}/notes
@app.get("/records/{id}/notes", tags=["Notes"])
def get_notes(id: str = Path(..., description="ID del registro")):
	data_path = os.path.join(os.path.dirname(__file__), "data", "mock_data.json")
	try:
		with open(data_path, "r", encoding="utf-8") as f:
			data = json.load(f)
		records = data.get("records", [])
	except Exception as e:
		return JSONResponse(status_code=500, content={"error": f"Error leyendo mock_data.json: {e}"})
	for rec in records:
		if rec.get("id") == id:
			notes = rec.get("notes", [])
			return {
				"data": notes,
				"meta": {"total": len(notes)}
			}
	return JSONResponse(status_code=404, content={"error": "Record not found"})


# POST /records/{id}/notes
@app.post("/records/{id}/notes", status_code=201, tags=["Notes"])
def add_note(
	id: str = Path(..., description="ID del registro"),
	note: NoteCreate = Body(...)
):
	data_path = os.path.join(os.path.dirname(__file__), "data", "mock_data.json")
	try:
		with open(data_path, "r", encoding="utf-8") as f:
			data = json.load(f)
		records = data.get("records", [])
	except Exception as e:
		return JSONResponse(status_code=500, content={"error": f"Error leyendo mock_data.json: {e}"})
	for idx, rec in enumerate(records):
		if rec.get("id") == id:
			if not note.content or not note.content.strip():
				return JSONResponse(status_code=422, content={"error": "Validation error", "details": {"content": "Content is required"}})
			new_note = {
				"id": str(uuid4()),
				"record_id": id,
				"content": note.content,
				"created_at": datetime.utcnow().isoformat() + "Z"
			}
			rec.setdefault("notes", []).append(new_note)
			rec["notes_count"] = len(rec["notes"])
			records[idx] = rec
			data["records"] = records
			try:
				with open(data_path, "w", encoding="utf-8") as f:
					json.dump(data, f, ensure_ascii=False, indent=2)
			except Exception as e:
				return JSONResponse(status_code=500, content={"error": f"Error guardando mock_data.json: {e}"})
			return new_note
	return JSONResponse(status_code=404, content={"error": "Record not found"})


# DELETE /records/{id}/notes/{note_id}
@app.delete("/records/{id}/notes/{note_id}", status_code=204, tags=["Notes"])
def delete_note(
	id: str = Path(..., description="ID del registro"),
	note_id: str = Path(..., description="ID de la nota")
):
	data_path = os.path.join(os.path.dirname(__file__), "data", "mock_data.json")
	try:
		with open(data_path, "r", encoding="utf-8") as f:
			data = json.load(f)
		records = data.get("records", [])
	except Exception as e:
		return JSONResponse(status_code=500, content={"error": f"Error leyendo mock_data.json: {e}"})
	for ridx, rec in enumerate(records):
		if rec.get("id") == id:
			notes = rec.get("notes", [])
			for nidx, note in enumerate(notes):
				if note.get("id") == note_id:
					del notes[nidx]
					rec["notes"] = notes
					rec["notes_count"] = len(notes)
					records[ridx] = rec
					data["records"] = records
					try:
						with open(data_path, "w", encoding="utf-8") as f:
							json.dump(data, f, ensure_ascii=False, indent=2)
					except Exception as e:
						return JSONResponse(status_code=500, content={"error": f"Error guardando mock_data.json: {e}"})
					return Response(status_code=204)
			return JSONResponse(status_code=404, content={"error": "Note not found"})
	return JSONResponse(status_code=404, content={"error": "Record not found"})