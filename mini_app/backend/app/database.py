# -*- coding: utf-8 -*-
"""
Database ulanish va modellar
"""
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager
from .config import DATABASE_NAME


@contextmanager
def get_db():
    """Database connection context manager (xatoda rollback qiladi)"""
    conn = sqlite3.connect(DATABASE_NAME, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        # SQLite concurrent yozuv uchun WAL va busy timeout
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA foreign_keys=ON")
        yield conn
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()


class Database:
    """Database operatsiyalari"""
    
    # ==================== SOZLAMALAR ====================
    
    @staticmethod
    def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
        """Sozlamani olish"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            result = cursor.fetchone()
            return result[0] if result else default
    
    @staticmethod
    def set_setting(key: str, value: str) -> None:
        """Sozlamani o'zgartirish"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value, updated_at) 
                VALUES (?, ?, ?)
            ''', (key, value, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
    
    @staticmethod
    def get_all_settings() -> Dict[str, str]:
        """Barcha sozlamalarni olish"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM settings")
            results = cursor.fetchall()
            return {row[0]: row[1] for row in results}
    
    # ==================== FOYDALANUVCHILAR ====================
    
    @staticmethod
    def get_user(user_id: int) -> Optional[Dict[str, Any]]:
        """Foydalanuvchi ma'lumotlarini olish"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = cursor.fetchone()
            if user:
                return dict(user)
            return None
    
    @staticmethod
    def add_user(user_id: int, username: str, full_name: str, referral_id: Optional[int] = None) -> bool:
        """Yangi foydalanuvchi qo'shish (referral bonus'lar atomic tarzda qo'shiladi)"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
            if cursor.fetchone() is None:
                cursor.execute('''
                    INSERT INTO users (user_id, username, full_name, referral_id, created_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, username, full_name, referral_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

                if referral_id:
                    try:
                        bonus = int(Database.get_setting('referral_bonus', '500') or '500')
                    except (TypeError, ValueError):
                        bonus = 500
                    # O'z-o'ziga referral qilib bo'lmaydi
                    if referral_id != user_id:
                        # Referrerga bonus
                        cursor.execute('''
                            UPDATE users
                            SET referral_count = referral_count + 1,
                                balance = balance + ?,
                                referral_earnings = referral_earnings + ?
                            WHERE user_id = ?
                        ''', (bonus, bonus, referral_id))
                        # Yangi foydalanuvchiga bonus (mavjud balansga QO'SHILADI, overwrite emas)
                        cursor.execute('''
                            UPDATE users SET balance = balance + ?
                            WHERE user_id = ?
                        ''', (bonus, user_id))

                conn.commit()
                return True
            return False
    
    @staticmethod
    def get_balance(user_id: int) -> float:
        """Balansni olish"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            return result[0] if result else 0
    
    @staticmethod
    def update_balance(user_id: int, amount: float) -> bool:
        """
        Balansni yangilash — atomic. Ayirish paytida yetarli mablag' bo'lmasa False qaytaradi
        (balans manfiyga tushmaydi). Yutish — True qaytaradi.
        """
        with get_db() as conn:
            cursor = conn.cursor()
            if amount < 0:
                # Atomic decrement: faqat balans >= |amount| bo'lsa ayiriladi
                cursor.execute(
                    '''
                    UPDATE users
                    SET balance = balance + ?
                    WHERE user_id = ? AND balance + ? >= 0
                    ''',
                    (amount, user_id, amount),
                )
                success = cursor.rowcount > 0
            else:
                cursor.execute(
                    'UPDATE users SET balance = balance + ? WHERE user_id = ?',
                    (amount, user_id),
                )
                success = cursor.rowcount > 0
            conn.commit()
            return success
    
    @staticmethod
    def get_referral_stats(user_id: int) -> Tuple[int, float]:
        """Referal statistikasini olish"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT referral_count, referral_earnings FROM users WHERE user_id = ?
            ''', (user_id,))
            result = cursor.fetchone()
            return (result[0], result[1]) if result else (0, 0)
    
    @staticmethod
    def get_referrals(user_id: int) -> List[Dict[str, Any]]:
        """Foydalanuvchining referallarini olish"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, username, full_name, created_at 
                FROM users WHERE referral_id = ?
                ORDER BY created_at DESC
            ''', (user_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    # ==================== BUYURTMALAR ====================
    
    @staticmethod
    def add_order(user_id: int, service_type: str, link: str, quantity: int, price: float) -> int:
        """Yangi buyurtma qo'shish"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO orders (user_id, service_type, link, quantity, price, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, service_type, link, quantity, price, 'pending', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            return cursor.lastrowid
    
    @staticmethod
    def get_user_orders(user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Foydalanuvchi buyurtmalarini olish"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT ?
            ''', (user_id, limit))
            return [dict(row) for row in cursor.fetchall()]
    
    @staticmethod
    def get_order(order_id: int) -> Optional[Dict[str, Any]]:
        """Bitta buyurtmani olish"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()
            if order:
                return dict(order)
            return None
    
    @staticmethod
    def update_order_status(order_id: int, status: str) -> None:
        """Buyurtma holatini yangilash"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
            conn.commit()
    
    @staticmethod
    def update_order_api_id(order_id: int, api_order_id: int, panel_name: Optional[str] = None) -> None:
        """Buyurtmaga API order ID qo'shish"""
        with get_db() as conn:
            cursor = conn.cursor()
            if panel_name:
                cursor.execute("UPDATE orders SET api_order_id = ?, panel_name = ? WHERE id = ?", 
                             (api_order_id, panel_name, order_id))
            else:
                cursor.execute("UPDATE orders SET api_order_id = ? WHERE id = ?", (api_order_id, order_id))
            conn.commit()
    
    # ==================== TO'LOVLAR ====================
    
    @staticmethod
    def add_payment(user_id: int, amount: float, method: str) -> int:
        """Yangi to'lov qo'shish"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO payments (user_id, amount, method, created_at)
                VALUES (?, ?, ?, ?)
            ''', (user_id, amount, method, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            return cursor.lastrowid
    
    @staticmethod
    def get_user_payments(user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Foydalanuvchi to'lovlarini olish"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM payments WHERE user_id = ? ORDER BY created_at DESC LIMIT ?
            ''', (user_id, limit))
            return [dict(row) for row in cursor.fetchall()]
    
    @staticmethod
    def get_payment(payment_id: int) -> Optional[Dict[str, Any]]:
        """Bitta to'lovni olish"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
            payment = cursor.fetchone()
            if payment:
                return dict(payment)
            return None
    
    @staticmethod
    def update_payment_status(payment_id: int, status: str) -> None:
        """To'lov holatini yangilash"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE payments SET status = ? WHERE id = ?", (status, payment_id))
            conn.commit()
    
    # ==================== PREMIUM ====================
    
    @staticmethod
    def add_premium_request(user_id: int, phone: str, months: int, price: float) -> int:
        """Premium so'rov qo'shish"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO premium_requests (user_id, phone, months, price, status, created_at)
                VALUES (?, ?, ?, ?, 'pending', ?)
            ''', (user_id, phone, months, price, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            return cursor.lastrowid
    
    @staticmethod
    def get_user_premium(user_id: int) -> Optional[Dict[str, Any]]:
        """Foydalanuvchining faol premium obunasini olish"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM premium_subscriptions 
                WHERE user_id = ? AND status = 'active'
                ORDER BY end_date DESC LIMIT 1
            ''', (user_id,))
            premium = cursor.fetchone()
            if premium:
                return dict(premium)
            return None
    
    # ==================== CLICK TO'LOVLARI ====================
    
    @staticmethod
    def init_click_payments_table():
        """Click to'lovlar jadvalini yaratish"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS click_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    status TEXT DEFAULT 'pending',
                    click_trans_id INTEGER,
                    click_paydoc_id INTEGER,
                    error_code INTEGER,
                    created_at TEXT,
                    completed_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            ''')
            conn.commit()
    
    @staticmethod
    def add_click_payment(user_id: int, amount: float) -> int:
        """Yangi Click to'lov yaratish"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO click_payments (user_id, amount, status, created_at)
                VALUES (?, ?, 'pending', ?)
            ''', (user_id, amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            return cursor.lastrowid
    
    @staticmethod
    def get_click_payment(payment_id: int) -> Optional[Dict[str, Any]]:
        """Click to'lovni olish"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM click_payments WHERE id = ?
            ''', (payment_id,))
            payment = cursor.fetchone()
            if payment:
                return dict(payment)
            return None
    
    @staticmethod
    def update_click_payment_status(
        payment_id: int, 
        status: str, 
        click_trans_id: int = None,
        click_paydoc_id: int = None,
        error_code: int = None
    ):
        """Click to'lov holatini yangilash"""
        with get_db() as conn:
            cursor = conn.cursor()
            
            update_fields = ["status = ?"]
            values = [status]
            
            if click_trans_id:
                update_fields.append("click_trans_id = ?")
                values.append(click_trans_id)
            
            if click_paydoc_id:
                update_fields.append("click_paydoc_id = ?")
                values.append(click_paydoc_id)
            
            if error_code is not None:
                update_fields.append("error_code = ?")
                values.append(error_code)
            
            if status == 'completed':
                update_fields.append("completed_at = ?")
                values.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            
            values.append(payment_id)
            
            query = f"UPDATE click_payments SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(query, values)
            conn.commit()
    
    @staticmethod
    def get_user_click_payments(user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Foydalanuvchining Click to'lovlarini olish"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM click_payments 
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (user_id, limit))
            return [dict(row) for row in cursor.fetchall()]
    
    # ==================== STATISTIKA ====================
    
    @staticmethod
    def get_statistics() -> Dict[str, Any]:
        """Umumiy statistikani olish"""
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Foydalanuvchilar soni
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            # Bugungi foydalanuvchilar
            today = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("SELECT COUNT(*) FROM users WHERE created_at LIKE ?", (f"{today}%",))
            today_users = cursor.fetchone()[0]
            
            # Buyurtmalar
            cursor.execute("SELECT COUNT(*) FROM orders")
            total_orders = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM orders WHERE created_at LIKE ?", (f"{today}%",))
            today_orders = cursor.fetchone()[0]
            
            # Daromad
            cursor.execute("SELECT COALESCE(SUM(price), 0) FROM orders WHERE status = 'completed'")
            total_revenue = cursor.fetchone()[0]
            
            cursor.execute("SELECT COALESCE(SUM(price), 0) FROM orders WHERE status = 'completed' AND created_at LIKE ?", (f"{today}%",))
            today_revenue = cursor.fetchone()[0]
            
            # To'lovlar
            cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'kutilmoqda'")
            pending_payments = cursor.fetchone()[0]
            
            return {
                "total_users": total_users,
                "today_users": today_users,
                "total_orders": total_orders,
                "today_orders": today_orders,
                "total_revenue": total_revenue,
                "today_revenue": today_revenue,
                "pending_payments": pending_payments
            }
