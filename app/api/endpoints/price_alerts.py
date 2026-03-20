"""
API для уведомлений о снижении цены.

Позволяет пользователям:
- Создавать уведомления для отслеживания цены объекта
- Получать уведомления при снижении цены
- Управлять своими подписками
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime, timezone

from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.repositories import property as property_repository
from app.dependencies.auth import get_current_user, TokenData
from app.utils.logger import logger

router = APIRouter(prefix="/alerts", tags=["price-alerts"])


class PriceAlertCreate(BaseModel):
    """Запрос на создание уведомления о снижении цены."""
    property_id: int = Field(..., description="ID объекта для отслеживания")
    threshold_percent: float = Field(
        default=10.0,
        ge=1.0,
        le=50.0,
        description="Процент снижения цены для уведомления (1-50%)"
    )
    threshold_amount: Optional[float] = Field(
        None,
        ge=0,
        description="Абсолютное значение снижения цены (альтернатива проценту)"
    )
    notify_email: Optional[bool] = Field(True, description="Уведомлять по email")
    notify_push: Optional[bool] = Field(True, description="Уведомлять push-уведомлением")


class PriceAlertResponse(BaseModel):
    """Ответ с информацией об уведомлении."""
    id: int
    user_id: int
    property_id: int
    property_title: str
    property_price: float
    threshold_percent: float
    threshold_amount: Optional[float]
    current_price: float
    price_drop: Optional[float]
    is_triggered: bool
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]


class PriceAlertListResponse(BaseModel):
    """Ответ со списком уведомлений."""
    alerts: List[PriceAlertResponse]
    total: int


class PriceAlertUpdate(BaseModel):
    """Запрос на обновление уведомления."""
    threshold_percent: Optional[float] = Field(None, ge=1.0, le=50.0)
    threshold_amount: Optional[float] = Field(None, ge=0)
    notify_email: Optional[bool] = None
    notify_push: Optional[bool] = None
    is_active: Optional[bool] = None


# ============================================================================
# In-Memory хранилище для уведомлений (заменить на БД в production)
# ============================================================================

_price_alerts_db: Dict[int, dict] = {}
_price_alerts_counter = 1


async def create_price_alert_in_db(
    user_id: int,
    property_id: int,
    threshold_percent: float,
    threshold_amount: Optional[float],
    notify_email: bool,
    notify_push: bool,
) -> dict:
    """Создать уведомление в хранилище."""
    global _price_alerts_counter
    
    alert = {
        "id": _price_alerts_counter,
        "user_id": user_id,
        "property_id": property_id,
        "threshold_percent": threshold_percent,
        "threshold_amount": threshold_amount,
        "notify_email": notify_email,
        "notify_push": notify_push,
        "is_active": True,
        "is_triggered": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
    }
    
    _price_alerts_db[_price_alerts_counter] = alert
    _price_alerts_counter += 1
    
    return alert


async def get_user_alerts_from_db(user_id: int) -> List[dict]:
    """Получить все уведомления пользователя."""
    return [
        alert for alert in _price_alerts_db.values()
        if alert["user_id"] == user_id and alert["is_active"]
    ]


async def get_alert_by_id_from_db(alert_id: int, user_id: int) -> Optional[dict]:
    """Получить уведомление по ID."""
    alert = _price_alerts_db.get(alert_id)
    if alert and alert["user_id"] == user_id:
        return alert
    return None


async def update_alert_in_db(alert_id: int, update_data: dict) -> Optional[dict]:
    """Обновить уведомление."""
    alert = _price_alerts_db.get(alert_id)
    if alert:
        alert.update(update_data)
        alert["updated_at"] = datetime.now(timezone.utc)
        return alert
    return None


async def delete_alert_from_db(alert_id: int, user_id: int) -> bool:
    """Удалить уведомление."""
    alert = _price_alerts_db.get(alert_id)
    if alert and alert["user_id"] == user_id:
        alert["is_active"] = False
        alert["updated_at"] = datetime.now(timezone.utc)
        return True
    return False


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_price_alert(
    alert_data: PriceAlertCreate,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Создать уведомление о снижении цены объекта.
    
    Уведомление сработает когда цена объекта снизится на указанный процент
    или сумму.
    """
    # Проверяем существование объекта
    prop = await property_repository.get_property_by_id(db, alert_data.property_id)
    if not prop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Объект с ID {alert_data.property_id} не найден"
        )
    
    # Создаем уведомление
    alert = await create_price_alert_in_db(
        user_id=current_user.user_id,
        property_id=alert_data.property_id,
        threshold_percent=alert_data.threshold_percent,
        threshold_amount=alert_data.threshold_amount,
        notify_email=alert_data.notify_email,
        notify_push=alert_data.notify_push,
    )
    
    logger.info(
        f"Created price alert for user {current_user.user_id}: "
        f"property {alert_data.property_id}, threshold {alert_data.threshold_percent}%"
    )
    
    return {
        "message": "Уведомление создано",
        "alert_id": alert["id"],
        "property_id": alert["property_id"],
        "threshold_percent": alert["threshold_percent"],
        "current_price": prop.price,
        "target_price": prop.price * (1 - alert["threshold_percent"] / 100),
    }


@router.get("", response_model=PriceAlertListResponse)
async def get_price_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
) -> PriceAlertListResponse:
    """
    Получить все активные уведомления пользователя.
    
    Возвращает список уведомлений с текущей информацией об объектах.
    """
    alerts = await get_user_alerts_from_db(current_user.user_id)
    
    # Получаем информацию об объектах
    alert_responses = []
    for alert in alerts:
        prop = await property_repository.get_property_by_id(db, alert["property_id"])
        
        if prop:
            # Проверяем, сработало ли уведомление
            price_drop = prop.price - (prop.price * alert["threshold_percent"] / 100)
            is_triggered = False
            
            if alert["threshold_amount"]:
                # Проверяем по абсолютной сумме
                # Нужно сравнить с последней известной ценой
                pass
            
            alert_responses.append(PriceAlertResponse(
                id=alert["id"],
                user_id=alert["user_id"],
                property_id=alert["property_id"],
                property_title=prop.title,
                property_price=prop.price,
                threshold_percent=alert["threshold_percent"],
                threshold_amount=alert["threshold_amount"],
                current_price=prop.price,
                price_drop=None,
                is_triggered=is_triggered,
                is_active=alert["is_active"],
                created_at=alert["created_at"],
                updated_at=alert["updated_at"],
            ))
    
    return PriceAlertListResponse(
        alerts=alert_responses,
        total=len(alert_responses),
    )


@router.get("/{alert_id}", response_model=PriceAlertResponse)
async def get_price_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
) -> PriceAlertResponse:
    """
    Получить информацию о конкретном уведомлении.
    """
    alert = await get_alert_by_id_from_db(alert_id, current_user.user_id)
    
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Уведомление с ID {alert_id} не найдено"
        )
    
    # Получаем информацию об объекте
    prop = await property_repository.get_property_by_id(db, alert["property_id"])
    
    if not prop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Объект {alert['property_id']} не найден"
        )
    
    return PriceAlertResponse(
        id=alert["id"],
        user_id=alert["user_id"],
        property_id=alert["property_id"],
        property_title=prop.title,
        property_price=prop.price,
        threshold_percent=alert["threshold_percent"],
        threshold_amount=alert["threshold_amount"],
        current_price=prop.price,
        price_drop=None,
        is_triggered=alert["is_triggered"],
        is_active=alert["is_active"],
        created_at=alert["created_at"],
        updated_at=alert["updated_at"],
    )


@router.put("/{alert_id}", response_model=Dict[str, Any])
async def update_price_alert(
    alert_id: int,
    update_data: PriceAlertUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Обновить параметры уведомления.
    
    Можно изменить порог срабатывания, способы уведомления или активировать/деактивировать.
    """
    alert = await get_alert_by_id_from_db(alert_id, current_user.user_id)
    
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Уведомление с ID {alert_id} не найдено"
        )
    
    # Обновляем данные
    update_dict = update_data.model_dump(exclude_unset=True)
    updated_alert = await update_alert_in_db(alert_id, update_dict)
    
    logger.info(f"Updated price alert {alert_id} for user {current_user.user_id}")
    
    return {
        "message": "Уведомление обновлено",
        "alert_id": alert_id,
        "updated_fields": list(update_dict.keys()),
    }


@router.delete("/{alert_id}", response_model=Dict[str, Any])
async def delete_price_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Удалить уведомление.
    
    Удаляет уведомление о снижении цены.
    """
    success = await delete_alert_from_db(alert_id, current_user.user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Уведомление с ID {alert_id} не найдено"
        )
    
    logger.info(f"Deleted price alert {alert_id} for user {current_user.user_id}")
    
    return {
        "message": "Уведомление удалено",
        "alert_id": alert_id,
    }


@router.post("/check", response_model=Dict[str, Any])
async def check_price_alerts(
    property_id: Optional[int] = Query(None, description="Проверить конкретный объект"),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Проверить срабатывание уведомлений.
    
    Проверяет все активные уведомления и возвращает сработавшие.
    """
    from app.db.models.property import PropertyPriceHistory
    
    # Получаем все активные уведомления пользователя
    alerts = await get_user_alerts_from_db(current_user.user_id)
    
    triggered_alerts = []
    
    for alert in alerts:
        # Получаем объект
        prop = await property_repository.get_property_by_id(db, alert["property_id"])
        if not prop:
            continue
        
        # Если указан конкретный property_id, проверяем только его
        if property_id and prop.id != property_id:
            continue
        
        # Получаем историю цен
        history = await property_repository.get_property_price_history(db, prop.id, limit=1)
        
        if history:
            last_entry = history[0]
            old_price = last_entry.old_price or 0
            new_price = last_entry.new_price or 0
            
            if old_price > 0 and new_price > 0:
                price_drop_percent = ((old_price - new_price) / old_price) * 100
                
                # Проверяем срабатывание
                if price_drop_percent >= alert["threshold_percent"]:
                    triggered_alerts.append({
                        "alert_id": alert["id"],
                        "property_id": prop.id,
                        "property_title": prop.title,
                        "old_price": old_price,
                        "new_price": new_price,
                        "drop_percent": round(price_drop_percent, 2),
                        "threshold_percent": alert["threshold_percent"],
                        "notify_email": alert["notify_email"],
                        "notify_push": alert["notify_push"],
                    })
                    
                    # Помечаем как сработавшее
                    await update_alert_in_db(alert["id"], {"is_triggered": True})
    
    return {
        "checked_alerts": len(alerts),
        "triggered_count": len(triggered_alerts),
        "triggered_alerts": triggered_alerts,
    }


@router.get("/stats", response_model=Dict[str, Any])
async def get_price_alert_stats(
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Получить статистику уведомлений пользователя.
    """
    alerts = await get_user_alerts_from_db(current_user.user_id)
    
    total = len(alerts)
    active = sum(1 for a in alerts if a["is_active"])
    triggered = sum(1 for a in alerts if a["is_triggered"])
    
    # Средний порог
    avg_threshold = sum(a["threshold_percent"] for a in alerts) / total if total > 0 else 0
    
    return {
        "total_alerts": total,
        "active_alerts": active,
        "triggered_alerts": triggered,
        "average_threshold_percent": round(avg_threshold, 2),
        "notification_methods": {
            "email": sum(1 for a in alerts if a["notify_email"]),
            "push": sum(1 for a in alerts if a["notify_push"]),
        },
    }
