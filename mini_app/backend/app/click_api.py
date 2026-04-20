# -*- coding: utf-8 -*-
"""
Click to'lov tizimi API integratsiyasi

Click API dokumentatsiyasi: https://docs.click.uz/

Click API ikkita qismdan iborat:
1. Prepare - To'lov tayyorlash (to'lov yaratiladi)
2. Complete - To'lov yakunlash (muvaffaqiyatli to'lov)

MUHIM: Click merchant ID va secret key'ni .env fayliga qo'shing:
CLICK_MERCHANT_ID=your_merchant_id
CLICK_SERVICE_ID=your_service_id  
CLICK_SECRET_KEY=your_secret_key
"""
import hashlib
import hmac
import time
from typing import Optional, Dict, Any
from datetime import datetime
from .config import CLICK_MERCHANT_ID, CLICK_SERVICE_ID, CLICK_SECRET_KEY
from .database import Database


class ClickAPI:
    """Click to'lov tizimi API"""
    
    # Click xato kodlari
    ERROR_CODES = {
        0: "Muvaffaqiyat",
        -1: "SIGN tekshiruvi muvaffaqiyatsiz",
        -2: "Noto'g'ri to'lov miqdori", 
        -3: "To'lov allaqachon amalga oshirilgan",
        -4: "To'lov topilmadi",
        -5: "So'rov foydalanuvchi tomonidan bekor qilindi",
        -6: "Tranzaksiya mavjud emas",
        -7: "Noto'g'ri so'rov",
        -8: "Xizmat vaqtincha mavjud emas",
        -9: "Buyurtma topilmadi"
    }
    
    @staticmethod
    def generate_sign(click_trans_id: int, service_id: int, secret_key: str, 
                      merchant_trans_id: str, amount: float, action: int,
                      sign_time: str) -> str:
        """
        Click uchun SIGN yaratish
        
        Click SIGN algoritmi:
        md5(click_trans_id + service_id + SECRET_KEY + merchant_trans_id + amount + action + sign_time)
        """
        sign_string = f"{click_trans_id}{service_id}{secret_key}{merchant_trans_id}{amount}{action}{sign_time}"
        return hashlib.md5(sign_string.encode()).hexdigest()
    
    @staticmethod
    def verify_sign(click_trans_id: int, service_id: int, merchant_trans_id: str,
                    amount: float, action: int, sign_time: str, sign: str) -> bool:
        """
        Click SIGN tekshirish (constant-time compare — timing hujumiga qarshi).
        """
        if not CLICK_SECRET_KEY:
            # Kalit sozlanmagan bo'lsa — hech qachon true qaytarmaymiz.
            return False
        if not sign or len(sign) != 32:
            return False
        expected_sign = ClickAPI.generate_sign(
            click_trans_id, service_id, CLICK_SECRET_KEY,
            merchant_trans_id, amount, action, sign_time
        )
        return hmac.compare_digest(expected_sign.lower(), sign.lower())
    
    @staticmethod
    def create_payment(user_id: int, amount: float) -> Dict[str, Any]:
        """
        Click to'lov yaratish
        
        Returns:
            dict: {
                'success': bool,
                'payment_id': int,
                'payment_url': str,  # Foydalanuvchi shu URLga o'tadi
                'error': str (agar xato bo'lsa)
            }
        """
        if amount < 1000:
            return {
                'success': False,
                'error': "Minimal to'lov miqdori 1000 so'm"
            }
        
        # Bazaga to'lov qo'shish
        payment_id = Database.add_click_payment(
            user_id=user_id,
            amount=amount
        )
        
        if not payment_id:
            return {
                'success': False,
                'error': "To'lov yaratishda xatolik"
            }
        
        # Click to'lov URL yaratish
        # Click standart to'lov URL formati
        payment_url = (
            f"https://my.click.uz/services/pay"
            f"?service_id={CLICK_SERVICE_ID}"
            f"&merchant_id={CLICK_MERCHANT_ID}"
            f"&amount={int(amount)}"
            f"&transaction_param={payment_id}"
            f"&return_url=https://t.me/your_bot"  # Telegram botga qaytish
        )
        
        return {
            'success': True,
            'payment_id': payment_id,
            'payment_url': payment_url,
            'amount': amount
        }
    
    @staticmethod
    def prepare(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Click Prepare so'rovi - to'lov tayyorlash
        
        Click shu endpointga quyidagi ma'lumotlarni yuboradi:
        - click_trans_id: Click tranzaksiya ID
        - service_id: Merchant service ID
        - click_paydoc_id: Click to'lov hujjati ID
        - merchant_trans_id: Bizning to'lov ID
        - amount: To'lov miqdori
        - action: 0 (Prepare)
        - error: Click xatosi (agar bor bo'lsa)
        - error_note: Xato tavsifi
        - sign_time: Imzo vaqti
        - sign_string: MD5 imzo
        """
        try:
            click_trans_id = int(data.get('click_trans_id', 0))
            service_id = int(data.get('service_id', 0))
            merchant_trans_id = str(data.get('merchant_trans_id', ''))
            amount = float(data.get('amount', 0))
            action = int(data.get('action', 0))
            sign_time = str(data.get('sign_time', ''))
            sign = str(data.get('sign_string', ''))
            
            # SIGN tekshirish
            if not ClickAPI.verify_sign(click_trans_id, service_id, merchant_trans_id,
                                        amount, action, sign_time, sign):
                return {
                    'error': -1,
                    'error_note': 'SIGN tekshiruvi muvaffaqiyatsiz'
                }
            
            # To'lovni bazadan olish
            payment = Database.get_click_payment(int(merchant_trans_id))
            
            if not payment:
                return {
                    'error': -4,
                    'error_note': "To'lov topilmadi"
                }
            
            # To'lov miqdorini tekshirish
            if abs(payment['amount'] - amount) > 1:  # 1 so'm tolerans
                return {
                    'error': -2,
                    'error_note': "Noto'g'ri to'lov miqdori"
                }
            
            # To'lov allaqachon amalga oshirilganmi tekshirish
            if payment['status'] == 'completed':
                return {
                    'error': -3,
                    'error_note': "To'lov allaqachon amalga oshirilgan"
                }
            
            # To'lovni prepare holatiga o'tkazish
            Database.update_click_payment_status(
                payment_id=int(merchant_trans_id),
                status='preparing',
                click_trans_id=click_trans_id,
                click_paydoc_id=int(data.get('click_paydoc_id', 0))
            )
            
            return {
                'error': 0,
                'error_note': 'Success',
                'click_trans_id': click_trans_id,
                'merchant_trans_id': merchant_trans_id,
                'merchant_prepare_id': int(merchant_trans_id)  # Click shunga qarab complete qiladi
            }
            
        except Exception as e:
            print(f"Click Prepare xatolik: {e}")
            return {
                'error': -7,
                'error_note': f'Noto\'g\'ri so\'rov: {str(e)}'
            }
    
    @staticmethod
    def complete(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Click Complete so'rovi - to'lovni yakunlash
        
        Click shu endpointga prepare muvaffaqiyatli bo'lgandan keyin yuboradi:
        - click_trans_id: Click tranzaksiya ID
        - service_id: Merchant service ID
        - click_paydoc_id: Click to'lov hujjati ID
        - merchant_trans_id: Bizning to'lov ID
        - merchant_prepare_id: Prepare da qaytargan ID
        - amount: To'lov miqdori
        - action: 1 (Complete)
        - error: Click xatosi (0 = muvaffaqiyat)
        - error_note: Xato tavsifi
        - sign_time: Imzo vaqti
        - sign_string: MD5 imzo
        """
        try:
            click_trans_id = int(data.get('click_trans_id', 0))
            service_id = int(data.get('service_id', 0))
            merchant_trans_id = str(data.get('merchant_trans_id', ''))
            merchant_prepare_id = str(data.get('merchant_prepare_id', ''))
            amount = float(data.get('amount', 0))
            action = int(data.get('action', 1))
            error = int(data.get('error', 0))
            sign_time = str(data.get('sign_time', ''))
            sign = str(data.get('sign_string', ''))
            
            # SIGN tekshirish
            if not ClickAPI.verify_sign(click_trans_id, service_id, merchant_trans_id,
                                        amount, action, sign_time, sign):
                return {
                    'error': -1,
                    'error_note': 'SIGN tekshiruvi muvaffaqiyatsiz'
                }
            
            # To'lovni bazadan olish
            payment = Database.get_click_payment(int(merchant_trans_id))
            
            if not payment:
                return {
                    'error': -4,
                    'error_note': "To'lov topilmadi"
                }
            
            # Click xatosi bo'lsa
            if error != 0:
                Database.update_click_payment_status(
                    payment_id=int(merchant_trans_id),
                    status='cancelled',
                    error_code=error
                )
                return {
                    'error': -5,
                    'error_note': "To'lov bekor qilindi"
                }
            
            # To'lov allaqachon yakunlanganmi
            if payment['status'] == 'completed':
                return {
                    'error': -3,
                    'error_note': "To'lov allaqachon amalga oshirilgan"
                }
            
            # To'lovni yakunlash - balansga qo'shish
            Database.update_click_payment_status(
                payment_id=int(merchant_trans_id),
                status='completed'
            )
            
            # Foydalanuvchi balansiga qo'shish
            Database.update_balance(payment['user_id'], amount)
            
            return {
                'error': 0,
                'error_note': 'Success',
                'click_trans_id': click_trans_id,
                'merchant_trans_id': merchant_trans_id,
                'merchant_confirm_id': int(merchant_trans_id)
            }
            
        except Exception as e:
            print(f"Click Complete xatolik: {e}")
            return {
                'error': -7,
                'error_note': f'Noto\'g\'ri so\'rov: {str(e)}'
            }
    
    @staticmethod
    def get_payment_status(payment_id: int) -> Dict[str, Any]:
        """
        To'lov holatini olish
        """
        payment = Database.get_click_payment(payment_id)
        
        if not payment:
            return {
                'success': False,
                'error': "To'lov topilmadi"
            }
        
        return {
            'success': True,
            'payment_id': payment['id'],
            'amount': payment['amount'],
            'status': payment['status'],
            'created_at': payment.get('created_at', ''),
            'completed_at': payment.get('completed_at')
        }
