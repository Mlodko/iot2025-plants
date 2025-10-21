"""
FastAPI backend for the roslinki_IOT project.
Run
  uvicorn app:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Annotated, Any, Optional, List

from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from pydantic_settings import BaseSettings

from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, JSON, Float, ForeignKey, Text
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session

class Settings(BaseSettings):
    db_url: str = Field(default=os.environ.get("DB_URL", "sqlite:///./iot.db"))
    model_path: Optional[str] = Field(default=os.environ.get("MODEL_PATH"))
    cors_origins: List[str] = Field(default_factory=lambda: ["*"])  # tighten for prod

settings = Settings()

# ------------------------------
# Database setup
# ------------------------------
connect_args = {"check_same_thread": False} if settings.db_url.startswith("sqlite") else {}
engine = create_engine(settings.db_url, echo=False, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
Base = declarative_base()

# ------------------------------
# ORM Models
# ------------------------------
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
    status = Column(String, nullable=False, default="pending")  # pending | sent | ack | failed

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

# ------------------------------
# Pydantic Schemas
# ------------------------------
class DeviceCreate(BaseModel):
    name: str
    ip: Optional[str] = None
    mac: Optional[str] = None
    software_version: Optional[str] = None
    config_json: Optional[dict[str, Any]] = None

class DeviceRead(DeviceCreate):
    id: int
    last_seen: Optional[dt.datetime] = None
    model_config = ConfigDict(from_attributes=True)

class SensorCreate(BaseModel):
    device_id: int
    type: str
    unit: Optional[str] = None
    pin: Optional[str] = None
    meta_json: Optional[dict[str, Any]] = None

class SensorRead(SensorCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)

class ReadingCreate(BaseModel):
    sensor_id: int
    ts: dt.datetime
    value: float
    raw_json: Optional[dict[str, Any]] = None

class ReadingRead(ReadingCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)

class CommandCreate(BaseModel):
    device_id: int
    command: str
    payload_json: Optional[dict[str, Any]] = None
    scheduled_at: Optional[dt.datetime] = None

class CommandRead(CommandCreate):
    id: int
    created_at: dt.datetime
    sent_at: Optional[dt.datetime] = None
    status: str
    model_config = ConfigDict(from_attributes=True)

class CommandResultCreate(BaseModel):
    command_id: int
    status: str
    output_json: Optional[dict[str, Any]] = None
    error_msg: Optional[str] = None

class CommandResultRead(CommandResultCreate):
    id: int
    received_at: dt.datetime
    model_config = ConfigDict(from_attributes=True)

# ML Schemas
class MLInput(BaseModel):
    features: List[float] = Field(..., description="Flat list of numeric features for the model")

class MLOutput(BaseModel):
    output: List[float]
    backend: str

# ------------------------------
# Dependencies
# ------------------------------

def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

DB = Annotated[Session, Depends(get_db)]

# ------------------------------
# Simple Local ML Model Loader
# ------------------------------
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
                self.session = ort.InferenceSession(path, providers=["CPUExecutionProvider"])  # Pi-friendly
                self.backend = "onnxruntime"
            else:
                # Unknown extension; keep dummy
                pass
        except Exception as e:
            print(f"[LocalModel] Failed to load model from {path}: {e}")
            self.backend = "dummy"
            self.model = None
            self.session = None

    def predict(self, features: List[float]) -> List[float]:
        # sklearn-like API
        if self.backend == "sklearn-joblib" and self.model is not None:
            import numpy as np  # type: ignore
            x = np.array(features, dtype=float).reshape(1, -1)
            try:
                y = getattr(self.model, "predict_proba", getattr(self.model, "predict", None))
                if y is None:
                    raise AttributeError("Model has neither predict_proba nor predict")
                out = y(x)
                out = out.tolist()[0]
                if not isinstance(out, list):
                    out = [float(out)]
                return [float(v) for v in out]
            except Exception:
                y = self.model.predict(x)
                out = y.tolist()
                return [float(v) for v in (out[0] if isinstance(out, list) else [out])]
        # onnxruntime API
        if self.backend == "onnxruntime" and self.session is not None:
            import numpy as np  # type: ignore
            inputs = {self.session.get_inputs()[0].name: np.array([features], dtype=float)}
            preds = self.session.run(None, inputs)
            # flatten first output
            out = preds[0]
            try:
                return [float(v) for v in out.flatten().tolist()]
            except Exception:
                return [float(out)]
        # dummy passthrough: echo mean & last
        if not features:
            return [0.0]
        mean_val = sum(features) / len(features)
        return [mean_val, features[-1]]

model = LocalModel(settings.model_path)

# ------------------------------
# FastAPI app
# ------------------------------
app = FastAPI(title="roslinki_IOT API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------
# Utilities
# ------------------------------

def paginate(query, page: int, page_size: int):
    return query.offset((page - 1) * page_size).limit(page_size)

# ------------------------------
# Routes: Health & Info
# ------------------------------
@app.get("/health")
def health():
    return {
        "ok": True,
        "time": dt.datetime.utcnow().isoformat(),
        "db": settings.db_url.split(":")[0],
        "ml_backend": model.backend,
    }

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

# ------------------------------
# Routes: Devices
# ------------------------------
@app.post("/devices", response_model=DeviceRead)
def create_device(payload: DeviceCreate, db: DB):
    if db.query(Device).filter(Device.name == payload.name).first():
        raise HTTPException(status_code=400, detail="Device name already exists")
    dev = Device(**payload.model_dump())
    db.add(dev)
    db.commit()
    db.refresh(dev)
    return dev

@app.get("/devices", response_model=List[DeviceRead])
def list_devices(db: DB, page: int = 1, page_size: int = 50):
    q = db.query(Device).order_by(Device.id.asc())
    return paginate(q, page, page_size).all()

@app.get("/devices/{device_id}", response_model=DeviceRead)
def get_device(device_id: int, db: DB):
    dev = db.get(Device, device_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")
    return dev

@app.patch("/devices/{device_id}", response_model=DeviceRead)
def update_device(device_id: int, payload: DeviceCreate, db: DB):
    dev = db.get(Device, device_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(dev, k, v)
    db.commit()
    db.refresh(dev)
    return dev

@app.post("/devices/{device_id}/heartbeat", response_model=DeviceRead)
def device_heartbeat(device_id: int, db: DB):
    dev = db.get(Device, device_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")
    dev.last_seen = dt.datetime.utcnow()
    db.commit()
    db.refresh(dev)
    return dev

# ------------------------------
# Routes: Sensors
# ------------------------------
@app.post("/sensors", response_model=SensorRead)
def create_sensor(payload: SensorCreate, db: DB):
    if not db.get(Device, payload.device_id):
        raise HTTPException(status_code=400, detail="Device does not exist")
    s = Sensor(**payload.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return s

@app.get("/sensors", response_model=List[SensorRead])
def list_sensors(db: DB, device_id: Optional[int] = None, page: int = 1, page_size: int = 100):
    q = db.query(Sensor)
    if device_id is not None:
        q = q.filter(Sensor.device_id == device_id)
    q = q.order_by(Sensor.id.asc())
    return paginate(q, page, page_size).all()

# ------------------------------
# Routes: Readings
# ------------------------------
@app.post("/readings", response_model=ReadingRead)
def create_reading(payload: ReadingCreate, db: DB):
    if not db.get(Sensor, payload.sensor_id):
        raise HTTPException(status_code=400, detail="Sensor does not exist")
    r = Reading(**payload.model_dump())
    db.add(r)
    db.commit()
    db.refresh(r)
    return r

class ReadingsBulkIn(BaseModel):
    items: List[ReadingCreate] = Field(..., min_items=1, max_items=1000)

class ReadingsBulkOut(BaseModel):
    inserted: int

@app.post("/readings/bulk", response_model=ReadingsBulkOut)
def create_readings_bulk(payload: ReadingsBulkIn, db: DB):
    count = 0
    for rc in payload.items:
        if not db.get(Sensor, rc.sensor_id):
            raise HTTPException(status_code=400, detail=f"Sensor {rc.sensor_id} does not exist")
        db.add(Reading(**rc.model_dump()))
        count += 1
    db.commit()
    return ReadingsBulkOut(inserted=count)

@app.get("/readings", response_model=List[ReadingRead])
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

# ------------------------------
# Routes: Commands
# ------------------------------
@app.post("/commands", response_model=CommandRead)
def create_command(payload: CommandCreate, bg: BackgroundTasks, db: DB):
    if not db.get(Device, payload.device_id):
        raise HTTPException(status_code=400, detail="Device does not exist")
    cmd = Command(**payload.model_dump())
    db.add(cmd)
    db.commit()
    db.refresh(cmd)
    # optional: enqueue background dispatcher stub
    bg.add_task(_maybe_dispatch_command, cmd.id)
    return cmd

async def _maybe_dispatch_command(command_id: int):
    # Placeholder for MQTT/HTTP push to the device. For now, mark as 'sent'.
    with SessionLocal() as db:
        cmd = db.get(Command, command_id)
        if not cmd:
            return
        cmd.sent_at = dt.datetime.utcnow()
        cmd.status = "sent"
        db.commit()

@app.get("/commands", response_model=List[CommandRead])
def list_commands(db: DB, device_id: Optional[int] = None, status: Optional[str] = None, page: int = 1, page_size: int = 100):
    q = db.query(Command)
    if device_id is not None:
        q = q.filter(Command.device_id == device_id)
    if status is not None:
        q = q.filter(Command.status == status)
    q = q.order_by(Command.created_at.desc())
    return paginate(q, page, page_size).all()

@app.post("/commands/{command_id}/results", response_model=CommandResultRead)
def add_command_result(command_id: int, payload: CommandResultCreate, db: DB):
    if command_id != payload.command_id:
        raise HTTPException(status_code=400, detail="command_id mismatch in path and body")
    if not db.get(Command, command_id):
        raise HTTPException(status_code=404, detail="Command not found")
    cr = CommandResult(**payload.model_dump())
    # Update command status to last known
    cmd = db.get(Command, command_id)
    if cmd:
        cmd.status = payload.status
    db.add(cr)
    db.commit()
    db.refresh(cr)
    return cr

# ------------------------------
# Routes: ML inference
# ------------------------------
@app.post("/ml/predict", response_model=MLOutput)
def ml_predict(payload: MLInput):
    out = model.predict(payload.features)
    return MLOutput(output=out, backend=model.backend)

# ------------------------------
# Quick seed route (dev only) — remove in production
# ------------------------------
@app.post("/dev/seed")
def dev_seed(db: DB):
    d = Device(name="raspi-gateway", ip="192.168.1.10", mac="AA:BB:CC:DD:EE:FF", software_version="1.0.0", last_seen=dt.datetime.utcnow())
    db.add(d)
    db.commit()
    db.refresh(d)
    s1 = Sensor(device_id=d.id, type="dht22_temp", unit="C", pin="GPIO4", meta_json={"location": "greenhouse"})
    s2 = Sensor(device_id=d.id, type="dht22_hum", unit="%", pin="GPIO4", meta_json={"location": "greenhouse"})
    db.add_all([s1, s2])
    db.commit()
    return {"device_id": d.id, "sensors": [s1.id, s2.id]}
