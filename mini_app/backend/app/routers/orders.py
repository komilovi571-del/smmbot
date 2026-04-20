# -*- coding: utf-8 -*-
"""
Buyurtma endpointlari
"""
from fastapi import APIRouter, Depends, HTTPException, Body, Request
from typing import Dict, Any, List
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..auth import get_current_user
from ..database import Database
from ..services import get_service_info, get_best_price
from ..smm_api import smm_api
from ..models import OrderCreate, OrderResponse

router = APIRouter(prefix="/orders", tags=["orders"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/create", response_model=OrderResponse)
@limiter.limit("5/minute")
async def create_order(
    request: Request,
    order: OrderCreate,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Yangi buyurtma yaratish.

    Poydon tartib (atomic + refundable):
    1) Xizmat + miqdorni tekshirish
    2) Balansni ATOMIC tarzda ayirish (rowcount orqali mablag' yetarliligini aniqlaymiz)
    3) SMM Panelga so'rov yuborish — agar xato bo'lsa pulni QAYTARAMIZ
    4) Buyurtmani bazaga yozish — agar yozishda xato bo'lsa ham pulni qaytaramiz
    """
    # Xizmatni tekshirish
    service = get_service_info(order.service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Xizmat topilmadi")

    # Miqdorni tekshirish
    if order.quantity < service["min_quantity"]:
        raise HTTPException(
            status_code=400,
            detail=f"Minimal miqdor: {service['min_quantity']}"
        )

    if order.quantity > service["max_quantity"]:
        raise HTTPException(
            status_code=400,
            detail=f"Maksimal miqdor: {service['max_quantity']}"
        )

    # Narxni hisoblash
    price_per_1000 = service["price_per_1000"]
    total_price = int((order.quantity / 1000) * price_per_1000)

    # Minimal narx
    if total_price < 100:
        total_price = 100

    # Panel ma'lumotlari
    panel_name = service.get("panel")
    panel_service_id = service.get("panel_service_id")
    if not panel_name or not panel_service_id:
        raise HTTPException(status_code=500, detail="Panel xizmati mavjud emas")

    # 1) ATOMIC debit — agar yetarli bo'lmasa False qaytaradi (balans saqlanadi)
    debited = Database.update_balance(user["user_id"], -total_price)
    if not debited:
        current_balance = Database.get_balance(user["user_id"])
        raise HTTPException(
            status_code=400,
            detail=f"Balans yetarli emas. Kerak: {total_price:,} so'm, Mavjud: {current_balance:,} so'm"
        )

    # 2) SMM Panelga so'rov — har qanday xatoda pul qaytariladi
    try:
        result = await smm_api.add_order(panel_name, panel_service_id, order.link, order.quantity)
    except Exception as e:
        Database.update_balance(user["user_id"], total_price)  # refund
        raise HTTPException(status_code=502, detail=f"Panel bilan aloqa xatosi: {e}")

    if not isinstance(result, dict) or "error" in result:
        Database.update_balance(user["user_id"], total_price)  # refund
        err = result.get("error") if isinstance(result, dict) else "noma'lum"
        raise HTTPException(status_code=502, detail=f"Panel xatosi: {err}")

    api_order_id = result.get("order")
    if not api_order_id:
        Database.update_balance(user["user_id"], total_price)  # refund
        raise HTTPException(status_code=502, detail="Panel buyurtma ID qaytarmadi")

    # 3) Bazaga saqlash
    try:
        order_id = Database.add_order(
            user_id=user["user_id"],
            service_type=order.service_id,
            link=order.link,
            quantity=order.quantity,
            price=total_price
        )
        Database.update_order_api_id(order_id, int(api_order_id), panel_name)
    except Exception as e:
        # Pulni qaytaramiz. Panelda buyurtma yaratilgan — log uchun ID saqlab qolamiz.
        Database.update_balance(user["user_id"], total_price)
        raise HTTPException(
            status_code=500,
            detail=f"Buyurtma saqlashda xatolik (panel order={api_order_id}): {e}"
        )

    return OrderResponse(
        id=order_id,
        service_type=order.service_id,
        service_name=service["name"],
        link=order.link,
        quantity=order.quantity,
        price=total_price,
        status="pending",
        created_at="",
        api_order_id=int(api_order_id),
        panel_name=panel_name
    )


@router.get("/my", response_model=List[OrderResponse])
async def get_my_orders(
    limit: int = 20,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Mening buyurtmalarim
    """
    orders = Database.get_user_orders(user["user_id"], limit)
    
    result = []
    for order in orders:
        service = get_service_info(order.get("service_type", ""))
        result.append(OrderResponse(
            id=order["id"],
            service_type=order.get("service_type", ""),
            service_name=service["name"] if service else order.get("service_type", ""),
            link=order.get("link", ""),
            quantity=order.get("quantity", 0),
            price=order.get("price", 0),
            status=order.get("status", "unknown"),
            created_at=order.get("created_at", ""),
            api_order_id=order.get("api_order_id"),
            panel_name=order.get("panel_name")
        ))
    
    return result


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order_details(
    order_id: int,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Buyurtma tafsilotlari
    """
    order = Database.get_order(order_id)
    
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    
    if order["user_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")
    
    service = get_service_info(order.get("service_type", ""))
    
    return OrderResponse(
        id=order["id"],
        service_type=order.get("service_type", ""),
        service_name=service["name"] if service else order.get("service_type", ""),
        link=order.get("link", ""),
        quantity=order.get("quantity", 0),
        price=order.get("price", 0),
        status=order.get("status", "unknown"),
        created_at=order.get("created_at", ""),
        api_order_id=order.get("api_order_id"),
        panel_name=order.get("panel_name")
    )


@router.get("/{order_id}/status")
async def get_order_status(
    order_id: int,
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Buyurtma holatini tekshirish
    """
    order = Database.get_order(order_id)
    
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    
    if order["user_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")
    
    # Panel dan status olish
    api_order_id = order.get("api_order_id")
    panel_name = order.get("panel_name")
    
    if api_order_id and panel_name:
        result = await smm_api.get_order_status(panel_name, api_order_id)
        
        if "status" in result:
            # Status yangilash
            new_status = result["status"].lower()
            if new_status in ["completed", "partial", "canceled", "refunded"]:
                Database.update_order_status(order_id, new_status)
            
            return {
                "order_id": order_id,
                "status": result.get("status"),
                "charge": result.get("charge"),
                "start_count": result.get("start_count"),
                "remains": result.get("remains")
            }
    
    return {
        "order_id": order_id,
        "status": order.get("status", "unknown")
    }
