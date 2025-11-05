from __future__ import annotations

import math
import asyncio
import json
import os
import datetime as dt
from typing import Any, Optional, List, Dict
try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated

# --- Pydantic 1.x (lokalnie tak masz) ---
from pydantic import BaseModel, Field, BaseSettings

from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, JSON, Float, ForeignKey, Text, event
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session
from fastapi import WebSocket, WebSocketDisconnect
from typing import Set
# =========================
# Settings
# =========================
class Settings(BaseSettings):
    db_url: str = Field(default=os.environ.get("DB_URL", "sqlite:///./iot.db"))
    model_path: Optional[str] = Field(default=os.environ.get("MODEL_PATH"))
    cors_origins: List[str] = Field(default_factory=lambda: ["*"])

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# >>> TU MUSI BYĆ INICJALIZACJA, ZANIM UŻYJESZ `settings` <<<
settings = Settings()

# =========================
# Database
# =========================
connect_args = {"check_same_thread": False} if settings.db_url.startswith("sqlite") else {}
engine = create_engine(settings.db_url, echo=False, future=True, connect_args=connect_args)

# Włącz FK dla SQLite
if settings.db_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
Base = declarative_base()

class Device(Base):
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    ip = Column(String, nullable=True)
    mac = Column(String, nullable=True, index=True)
    software_version = Column(String, nullable=True)
    last_seen = Column(DateTime, nullable=True, index=True)
    config_json = Column(JSON, nullable=True)

    sensors = relationship("Sensor", back_populates="device", cascade="all, delete-orphan")
    commands = relationship("Command", back_populates="device", cascade="all, delete-orphan")


class Sensor(Base):
    __tablename__ = "sensors"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String, nullable=False)
    unit = Column(String, nullable=True)
    pin = Column(String, nullable=True)
    meta_json = Column(JSON, nullable=True)

    device = relationship("Device", back_populates="sensors")
    readings = relationship("Reading", back_populates="sensor", cascade="all, delete-orphan")


class Reading(Base):
    __tablename__ = "readings"
    id = Column(Integer, primary_key=True, index=True)
    sensor_id = Column(Integer, ForeignKey("sensors.id", ondelete="CASCADE"), nullable=False, index=True)
    ts = Column(DateTime, nullable=False, index=True)
    value = Column(Float, nullable=False)
    raw_json = Column(JSON, nullable=True)

    sensor = relationship("Sensor", back_populates="readings")


class Command(Base):
    __tablename__ = "commands"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    command = Column(String, nullable=False)
    payload_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=dt.datetime.utcnow)
    scheduled_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    status = Column(String, nullable=False, default="pending")  # pending|sent|ack|failed

    device = relationship("Device", back_populates="commands")
    results = relationship("CommandResult", back_populates="command_rel", cascade="all, delete-orphan")


class CommandResult(Base):
    __tablename__ = "command_results"
    id = Column(Integer, primary_key=True, index=True)
    command_id = Column(Integer, ForeignKey("commands.id", ondelete="CASCADE"), nullable=False, index=True)
    received_at = Column(DateTime, nullable=False, default=dt.datetime.utcnow)
    status = Column(String, nullable=False)
    output_json = Column(JSON, nullable=True)
    error_msg = Column(Text, nullable=True)

    command_rel = relationship("Command", back_populates="results")


# =========================
# Pydantic Schemas (API I/O)
# =========================
class DeviceCreate(BaseModel):
    name: str
    ip: Optional[str] = None
    mac: Optional[str] = None
    software_version: Optional[str] = None
    config_json: Optional[Dict[str, Any]] = None


class DeviceRead(DeviceCreate):
    id: int
    last_seen: Optional[dt.datetime] = None

    class Config:
        orm_mode = True


class SensorCreate(BaseModel):
    device_id: int
    type: str
    unit: Optional[str] = None
    pin: Optional[str] = None
    meta_json: Optional[Dict[str, Any]] = None


class SensorRead(SensorCreate):
    id: int

    class Config:
        orm_mode = True


class ReadingCreate(BaseModel):
    sensor_id: int
    ts: dt.datetime
    value: float
    raw_json: Optional[Dict[str, Any]] = None


class ReadingRead(ReadingCreate):
    id: int

    class Config:
        orm_mode = True


class CommandCreate(BaseModel):
    device_id: int
    command: str
    payload_json: Optional[Dict[str, Any]] = None
    scheduled_at: Optional[dt.datetime] = None


class CommandRead(CommandCreate):
    id: int
    created_at: dt.datetime
    sent_at: Optional[dt.datetime] = None
    status: str

    class Config:
        orm_mode = True


class CommandResultCreate(BaseModel):
    command_id: int
    status: str
    output_json: Optional[Dict[str, Any]] = None
    error_msg: Optional[str] = None


class CommandResultRead(CommandResultCreate):
    id: int
    received_at: dt.datetime

    class Config:
        orm_mode = True


# ML schemas
class MLInput(BaseModel):
    features: List[float] = Field(..., description="Flat list of numeric features")


class MLOutput(BaseModel):
    output: List[float]
    backend: str

# =========================
# FastAPI app init
# =========================
app = FastAPI(title="roslinki_IOT API", version="0.1.0")
# =========================
# DB dependency
# =========================

from sqlalchemy import func

def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

DB = Annotated[Session, Depends(get_db)]



def _series_for_type(db: Session, sensor_type_like: str, limit_points: int = 50):
    """
    Zwraca (labels, values) dla PIERWSZEGO sensora, którego Sensor.type ILIKE %sensor_type_like%.
    labels – lista krótkich HH:MM, values – lista float.
    """
    sensor = (
        db.query(Sensor)
        .filter(Sensor.type.ilike(f"%{sensor_type_like}%"))
        .order_by(Sensor.id.asc())
        .first()
    )
    if not sensor:
        return [], []

    rows = (
        db.query(Reading.ts, Reading.value)
        .filter(Reading.sensor_id == sensor.id)
        .order_by(Reading.ts.desc())
        .limit(limit_points)
        .all()
    )
    rows = list(reversed(rows))  # rosnąco po czasie
    labels = [r.ts.strftime("%H:%M") for r in rows]
    values = [float(r.value) for r in rows]
    return labels, values

@app.get("/api/graphs/latest")
def graphs_latest(db: DB, points: int = 50):
    """
    Zwraca dane do 4 wykresów: temperature, humidity, soil, light.
    Bierzemy pierwszy pasujący sensor po nazwie typu (ILIKE).
    """
    t_lab, t_val = _series_for_type(db, "temp", points)
    h_lab, h_val = _series_for_type(db, "hum", points)
    s_lab, s_val = _series_for_type(db, "soil", points)
    l_lab, l_val = _series_for_type(db, "light", points)

    return {
        "temperature": {"labels": t_lab, "values": t_val},
        "humidity": {"labels": h_lab, "values": h_val},
        "soil": {"labels": s_lab, "values": s_val},
        "light": {"labels": l_lab, "values": l_val},
    }
import random

@app.post("/api/dev/seed_readings")
def dev_seed_readings(db: DB, points: int = 120):
    """
    Tworzy (jeśli brak) urządzenie + 4 sensory (temp/hum/soil/light) i dodaje 'points' pomiarów
    co minutę wstecz od teraz, z lekkim szumem losowym.
    """
    # 1) urządzenie
    dev = db.query(Device).filter(Device.name == "raspi-gateway").first()
    if not dev:
        dev = Device(
            name="raspi-gateway",
            ip="192.168.1.10",
            mac="AA:BB:CC:DD:EE:FF",
            software_version="1.0.0",
            last_seen=dt.datetime.utcnow(),
        )
        db.add(dev)
        db.commit()
        db.refresh(dev)

    # 2) sensory (jeśli brak)
    def get_or_create_sensor(stype: str, unit: str):
        s = (
            db.query(Sensor)
            .filter(Sensor.device_id == dev.id, Sensor.type == stype)
            .first()
        )
        if not s:
            s = Sensor(device_id=dev.id, type=stype, unit=unit, pin=None, meta_json={})
            db.add(s)
            db.commit()
            db.refresh(s)
        return s

    s_temp = get_or_create_sensor("dht22_temp", "C")
    s_hum  = get_or_create_sensor("dht22_hum", "%")
    s_soil = get_or_create_sensor("soil_moisture", "%")
    s_light= get_or_create_sensor("light_level", "lx")

    # 3) generujemy pomiary minute-by-minute
    now = dt.datetime.utcnow().replace(second=0, microsecond=0)
    base_temp = 23.0
    base_hum  = 52.0
    base_soil = 40.0
    base_light= 300.0

    # usuń stare, jeśli chcesz czysto (opcjonalnie – zakomentuj, by nie kasować)
    # db.query(Reading).filter(Reading.sensor_id.in_([s_temp.id, s_hum.id, s_soil.id, s_light.id])).delete(synchronize_session=False)
    # db.commit()

    items = []
    for i in range(points):
        ts = now - dt.timedelta(minutes=(points - 1 - i))
        # lekki trend / szum
        t = base_temp + 0.5*math.sin(i/10) + random.uniform(-0.3, 0.3)
        h = base_hum  + 2.0*math.sin(i/15) + random.uniform(-1.0, 1.0)
        sm= base_soil + 3.0*math.sin(i/18) + random.uniform(-1.0, 1.5)
        li= base_light+ 20.0*math.sin(i/8)  + random.uniform(-10.0, 10.0)

        items.extend([
            Reading(sensor_id=s_temp.id, ts=ts, value=float(t)),
            Reading(sensor_id=s_hum.id,  ts=ts, value=float(h)),
            Reading(sensor_id=s_soil.id, ts=ts, value=float(sm)),
            Reading(sensor_id=s_light.id,ts=ts, value=float(li)),
        ])

    db.add_all(items)
    db.commit()
    return {"inserted": len(items), "device_id": dev.id, "sensors": [s_temp.id, s_hum.id, s_soil.id, s_light.id]}

# =========================
# ML "model"
# =========================
class LocalModel:
    def __init__(self, path: Optional[str]):
        self.backend = "dummy"
        self.model = None
        self.session = None
        if not path:
            return
        try:
            if path.endswith((".pkl", ".joblib")):
                import joblib  # type: ignore
                self.model = joblib.load(path)
                self.backend = "sklearn-joblib"
            elif path.endswith(".onnx"):
                import onnxruntime as ort  # type: ignore
                self.session = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
                self.backend = "onnxruntime"
        except Exception as e:
            print(f"[LocalModel] Failed to load model from {path}: {e}")
            self.backend = "dummy"
            self.model = None
            self.session = None

    def predict(self, features: List[float]) -> List[float]:
        if not features:
            return [0.0]
        mean_val = sum(features) / len(features)
        return [mean_val, features[-1]]

model = LocalModel(settings.model_path)

# static (css/js/img/fonts)
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

# templates (HTML pages)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# CORS (for now allow all because LAN, can tighten later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# Helpers
# =========================
def paginate(query, page: int, page_size: int):
    return query.offset((page - 1) * page_size).limit(page_size)


# =========================
# Startup
# =========================
@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


# =========================
# HTML ROUTES (pages you open in browser)
# =========================
@app.get("/", response_class=HTMLResponse)
def dashboard_page(request: Request, db: DB):
    latest_readings = (
        db.query(Reading)
        .order_by(Reading.ts.desc())
        .limit(10)
        .all()
    )
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "latest_readings": latest_readings}
    )


@app.get("/devices_ui", response_class=HTMLResponse)
def devices_page(request: Request, db: DB):
    devices = db.query(Device).order_by(Device.id.asc()).all()
    return templates.TemplateResponse(
        "devices.html",
        {"request": request, "devices": devices}
    )


@app.get("/devices", response_class=HTMLResponse)
def devices_alias():
    return RedirectResponse("/devices_ui")


@app.get("/add_device", response_class=HTMLResponse)
def add_device_alias():
    return RedirectResponse("/add_device_ui")


@app.get("/graph", response_class=HTMLResponse)
def graph_alias():
    return RedirectResponse("/graph_ui")


@app.get("/add_device_ui", response_class=HTMLResponse)
def add_device_page(request: Request):
    return templates.TemplateResponse("add_device.html", {"request": request})


@app.get("/graph_ui", response_class=HTMLResponse)
def graph_page(request: Request):
    return templates.TemplateResponse("graph.html", {"request": request})


# =========================
# API ROUTES (AJAX from main.js)
# =========================

# Health/info
@app.get("/health")
def health():
    return {
        "ok": True,
        "time": dt.datetime.utcnow().isoformat(),
        "db": settings.db_url.split(":")[0],
        "ml_backend": model.backend,
    }


# Devices
@app.post("/api/devices", response_model=DeviceRead)
def create_device(payload: DeviceCreate, db: DB):
    if db.query(Device).filter(Device.name == payload.name).first():
        raise HTTPException(status_code=400, detail="Device name already exists")
    dev = Device(**payload.dict())
    db.add(dev)
    db.commit()
    db.refresh(dev)
    return dev


@app.get("/api/devices", response_model=List[DeviceRead])
def list_devices(db: DB, page: int = 1, page_size: int = 50):
    q = db.query(Device).order_by(Device.id.asc())
    return paginate(q, page, page_size).all()


@app.patch("/api/devices/{device_id}", response_model=DeviceRead)
def update_device(device_id: int, payload: DeviceCreate, db: DB):
    dev = db.get(Device, device_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")
    for k, v in payload.dict(exclude_unset=True).items():
        setattr(dev, k, v)
    db.commit()
    db.refresh(dev)
    return dev


@app.post("/api/devices/{device_id}/heartbeat", response_model=DeviceRead)
def device_heartbeat(device_id: int, db: DB):
    dev = db.get(Device, device_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")
    dev.last_seen = dt.datetime.utcnow()
    db.commit()
    db.refresh(dev)
    return dev


# Sensors
@app.post("/api/sensors", response_model=SensorRead)
def create_sensor(payload: SensorCreate, db: DB):
    if not db.get(Device, payload.device_id):
        raise HTTPException(status_code=400, detail="Device does not exist")
    s = Sensor(**payload.dict())
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@app.get("/api/sensors", response_model=List[SensorRead])
def list_sensors(db: DB, device_id: Optional[int] = None, page: int = 1, page_size: int = 100):
    q = db.query(Sensor)
    if device_id is not None:
        q = q.filter(Sensor.device_id == device_id)
    q = q.order_by(Sensor.id.asc())
    return paginate(q, page, page_size).all()


# Readings
class ReadingsBulkIn(BaseModel):
    items: List[ReadingCreate]


class ReadingsBulkOut(BaseModel):
    inserted: int



async def broadcast_reading(reading: Reading, db: Session):
    try:
        sensor = db.get(Sensor, reading.sensor_id)
        if not sensor:
            return
        payload = {
            "sensor_type": sensor.type,
            "sensor_id": sensor.id,
            "value": reading.value,
            "ts": reading.ts.isoformat(),
        }
        for client in list(active_clients):
            try:
                await client.send_text(json.dumps(payload))
            except Exception:
                active_clients.remove(client)
    except Exception as e:
        print("[WS] Broadcast error:", e)


@app.post("/api/readings", response_model=ReadingRead)
async def create_reading(payload: ReadingCreate, db: DB):
    if not db.get(Sensor, payload.sensor_id):
        raise HTTPException(status_code=400, detail="Sensor does not exist")
    r = Reading(**payload.dict())
    db.add(r)
    db.commit()
    db.refresh(r)

    # 🔥 Wyślij do wszystkich websocketowych klientów
    asyncio.create_task(broadcast_reading(r, db))

    return r


@app.post("/api/readings/bulk", response_model=ReadingsBulkOut)
def create_readings_bulk(payload: ReadingsBulkIn, db: DB):
    count = 0
    for rc in payload.items:
        if not db.get(Sensor, rc.sensor_id):
            raise HTTPException(status_code=400, detail=f"Sensor {rc.sensor_id} does not exist")
        db.add(Reading(**rc.dict()))
        count += 1
    db.commit()
    return ReadingsBulkOut(inserted=count)


@app.get("/api/readings", response_model=List[ReadingRead])
def list_readings(
    db: DB,
    sensor_id: Optional[int] = None,
    since: Optional[dt.datetime] = Query(None, description="ISO timestamp lower bound"),
    until: Optional[dt.datetime] = Query(None, description="ISO timestamp upper bound"),
    page: int = 1,
    page_size: int = 500,
):
    q = db.query(Reading)
    if sensor_id is not None:
        q = q.filter(Reading.sensor_id == sensor_id)
    if since is not None:
        q = q.filter(Reading.ts >= since)
    if until is not None:
        q = q.filter(Reading.ts <= until)
    q = q.order_by(Reading.ts.desc())
    return paginate(q, page, page_size).all()


# Commands / pump control, etc.
@app.post("/api/commands", response_model=CommandRead)
def create_command(payload: CommandCreate, bg: BackgroundTasks, db: DB):
    if not db.get(Device, payload.device_id):
        raise HTTPException(status_code=400, detail="Device does not exist")
    cmd = Command(**payload.dict())
    db.add(cmd)
    db.commit()
    db.refresh(cmd)
    bg.add_task(_maybe_dispatch_command, cmd.id)
    return cmd


async def _maybe_dispatch_command(command_id: int):
    with SessionLocal() as db:
        cmd = db.get(Command, command_id)
        if not cmd:
            return
        # e.g. send MQTT/HTTP to device here
        cmd.sent_at = dt.datetime.utcnow()
        cmd.status = "sent"
        db.commit()


@app.get("/api/commands", response_model=List[CommandRead])
def list_commands(
    db: DB,
    device_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 100
):
    q = db.query(Command)
    if device_id is not None:
        q = q.filter(Command.device_id == device_id)
    if status is not None:
        q = q.filter(Command.status == status)
    q = q.order_by(Command.created_at.desc())
    return paginate(q, page, page_size).all()


@app.post("/api/commands/{command_id}/results", response_model=CommandResultRead)
def add_command_result(command_id: int, payload: CommandResultCreate, db: DB):
    if command_id != payload.command_id:
        raise HTTPException(status_code=400, detail="command_id mismatch in path and body")
    if not db.get(Command, command_id):
        raise HTTPException(status_code=404, detail="Command not found")
    cr = CommandResult(**payload.dict())
    cmd = db.get(Command, command_id)
    if cmd:
        cmd.status = payload.status
    db.add(cr)
    db.commit()
    db.refresh(cr)
    return cr


# ML inference
@app.post("/api/ml/predict", response_model=MLOutput)
def ml_predict(payload: MLInput):
    out = model.predict(payload.features)
    return MLOutput(output=out, backend=model.backend)

@app.delete("/api/devices/{device_id}")
def delete_device(device_id: int, db: DB):
    dev = db.get(Device, device_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")
    db.delete(dev)  # relacje mają cascade="all, delete-orphan"; FK mają ondelete="CASCADE"
    db.commit()
    return {"deleted": True, "id": device_id}

# Dev seed (optional)
@app.get("/api/dev/debug_counts")
def dev_debug_counts(db: DB):
    return {
        "devices": db.query(Device).count(),
        "sensors": db.query(Sensor).count(),
        "readings": db.query(Reading).count(),
        "first_sensor_types": [s.type for s in db.query(Sensor).order_by(Sensor.id.asc()).limit(10)]
    }

@app.post("/api/dev/seed")
def dev_seed(db: DB):
    d = Device(
        name="raspi-gateway",
        ip="192.168.1.10",
        mac="AA:BB:CC:DD:EE:FF",
        software_version="1.0.0",
        last_seen=dt.datetime.utcnow()
    )
    db.add(d)
    db.commit()
    db.refresh(d)

    s1 = Sensor(device_id=d.id, type="dht22_temp", unit="C", pin="GPIO4", meta_json={"location": "greenhouse"})
    s2 = Sensor(device_id=d.id, type="dht22_hum", unit="%", pin="GPIO4", meta_json={"location": "greenhouse"})

    db.add_all([s1, s2])
    db.commit()

    return {"device_id": d.id, "sensors": [s1.id, s2.id]}


# Lista aktywnych klientów websocket
active_clients: Set[WebSocket] = set()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_clients.add(websocket)
    print("[WS] Client connected:", websocket.client)
    try:
        while True:
            await websocket.receive_text()  # ewentualne wiadomości od klienta (np. ping)
    except WebSocketDisconnect:
        print("[WS] Client disconnected:", websocket.client)
        active_clients.remove(websocket)
