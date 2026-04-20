import sqlite3
import logging
from contextlib import contextmanager
from config import DATABASE_NAME
from datetime import datetime

logger = logging.getLogger(__name__)

# ==================== DATABASE CONNECTION MANAGER ====================
@contextmanager
def get_db_connection():
    """
    Context manager for database connections.
    Ensures proper connection handling and automatic cleanup.
    Usage:
        with get_db_connection() as (conn, cursor):
            cursor.execute(...)
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME, timeout=30)
        conn.row_factory = sqlite3.Row  # Dict-like access to rows
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA foreign_keys=ON")
        cursor = conn.cursor()
        yield conn, cursor
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


@contextmanager
def get_db_transaction():
    """
    Context manager for database transactions.
    Automatically commits on success, rollbacks on error.
    Usage:
        with get_db_transaction() as (conn, cursor):
            cursor.execute(...)
            # Auto-commit on success
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA foreign_keys=ON")
        cursor = conn.cursor()
        yield conn, cursor
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Transaction error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def init_db():
    """Ma'lumotlar bazasini yaratish"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # Foydalanuvchilar jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            balance REAL DEFAULT 0,
            referral_id INTEGER,
            referral_count INTEGER DEFAULT 0,
            referral_earnings REAL DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            created_at TEXT,
            phone TEXT
        )
    ''')
    
    # Eski bazalar uchun: phone, api_order_id, panel_name ustunlarini qo'shish
    for alter_sql in (
        'ALTER TABLE users ADD COLUMN phone TEXT',
        'ALTER TABLE orders ADD COLUMN api_order_id INTEGER',
        'ALTER TABLE orders ADD COLUMN panel_name TEXT',
    ):
        try:
            cursor.execute(alter_sql)
        except Exception:
            pass  # Ustun allaqachon mavjud
    
    # Buyurtmalar jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            service_type TEXT,
            platform TEXT,
            link TEXT,
            quantity INTEGER,
            price REAL,
            status TEXT DEFAULT 'kutilmoqda',
            created_at TEXT,
            api_order_id INTEGER,
            panel_name TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # To'lovlar jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            method TEXT,
            status TEXT DEFAULT 'kutilmoqda',
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # ==================== INDEXLAR (TEZLIK UCHUN!) ====================
    # Buyurtmalar - user_id bo'yicha qidirish tezlashadi
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)')
    
    # Buyurtmalar - status bo'yicha qidirish (kutilmoqda, bajarildi, ...)
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)')
    
    # Buyurtmalar - sana bo'yicha qidirish (statistika uchun)
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at)')
    
    # Buyurtmalar - user_id + status kombinatsiyasi (eng ko'p ishlatiladi)
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_user_status ON orders(user_id, status)')
    
    # To'lovlar - user_id bo'yicha
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id)')
    
    # To'lovlar - status bo'yicha
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status)')
    
    # Foydalanuvchilar - is_banned bo'yicha
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_banned ON users(is_banned)')
    
    # Foydalanuvchilar - referral_id bo'yicha
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_referral ON users(referral_id)')
    
    # ==================== PREMIUM OBUNA JADVALI ====================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS premium_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            plan_type TEXT,
            months INTEGER,
            price REAL,
            start_date TEXT,
            end_date TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Premium obuna index
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_premium_user ON premium_subscriptions(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_premium_status ON premium_subscriptions(status)')
    
    # ==================== PREMIUM SO'ROVLAR JADVALI ====================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS premium_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            phone TEXT,
            months INTEGER,
            price REAL,
            status TEXT DEFAULT 'pending',
            admin_message_id INTEGER,
            created_at TEXT,
            processed_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_premium_requests_status ON premium_requests(status)')
    
    # ==================== CLICK TO'LOVLAR JADVALI ====================
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
    
    # Click to'lovlar indexlari
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_click_payments_user ON click_payments(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_click_payments_status ON click_payments(status)')
    
    # ==================== SOZLAMALAR JADVALI ====================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT
        )
    ''')
    
    # Standart sozlamalarni qo'shish (agar yo'q bo'lsa)
    default_settings = [
        ('usd_rate', '12900'),
        ('rub_rate', '140'),
        ('markup_percent', '20'),
        ('card_number', '9860 1234 5678 9012'),
        ('card_holder', 'ADMIN'),
        ('min_deposit', '5000'),
        ('referral_bonus', '500'),
        ('bot_active', '1')
    ]
    
    for key, value in default_settings:
        cursor.execute('''
            INSERT OR IGNORE INTO settings (key, value, updated_at) 
            VALUES (?, ?, ?)
        ''', (key, value, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    conn.commit()
    conn.close()


# ==================== SOZLAMALAR FUNKSIYALARI ====================

def get_setting(key, default=None):
    """Sozlamani olish"""
    try:
        with get_db_connection() as (conn, cursor):
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            result = cursor.fetchone()
            return result[0] if result else default
    except Exception as e:
        logger.error(f"get_setting error: {e}")
        return default


def set_setting(key, value):
    """Sozlamani o'zgartirish"""
    try:
        with get_db_transaction() as (conn, cursor):
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value, updated_at) 
                VALUES (?, ?, ?)
            ''', (key, value, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        return True
    except Exception as e:
        logger.error(f"set_setting error: {e}")
        return False


def get_all_settings():
    """Barcha sozlamalarni olish"""
    try:
        with get_db_connection() as (conn, cursor):
            cursor.execute("SELECT key, value FROM settings")
            results = cursor.fetchall()
            return {row[0]: row[1] for row in results}
    except Exception as e:
        logger.error(f"get_all_settings error: {e}")
        return {}


def add_user(user_id, username, full_name, referral_id=None):
    """Yangi foydalanuvchi qo'shish - transaction bilan"""
    try:
        with get_db_transaction() as (conn, cursor):
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
            if cursor.fetchone() is None:
                cursor.execute('''
                    INSERT INTO users (user_id, username, full_name, referral_id, created_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, username, full_name, referral_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                
                # Referal bonusi - sozlamalardan olish
                if referral_id:
                    # Bonus miqdorini settings dan olish
                    bonus = int(get_setting('referral_bonus', '500'))
                    
                    # Referal sonini oshirish
                    cursor.execute('''
                        UPDATE users SET referral_count = referral_count + 1 
                        WHERE user_id = ?
                    ''', (referral_id,))
                    
                    # Referal egasiga bonus
                    cursor.execute('''
                        UPDATE users SET balance = balance + ?, referral_earnings = referral_earnings + ?
                        WHERE user_id = ?
                    ''', (bonus, bonus, referral_id,))
                    
                    # Yangi foydalanuvchiga ham bonus
                    cursor.execute('''
                        UPDATE users SET balance = ?
                        WHERE user_id = ?
                    ''', (bonus, user_id,))
                
                return referral_id is not None
            return False
    except Exception as e:
        logger.error(f"add_user error: {e}")
        return False


def get_user(user_id):
    """Foydalanuvchi ma'lumotlarini olish"""
    try:
        with get_db_connection() as (conn, cursor):
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = cursor.fetchone()
            return tuple(user) if user else None
    except Exception as e:
        logger.error(f"get_user error: {e}")
        return None


def get_user_by_phone(phone):
    """Telefon raqam bo'yicha foydalanuvchini topish"""
    try:
        with get_db_connection() as (conn, cursor):
            # Telefon raqamni normalizatsiya qilish
            phone = phone.replace('+', '').replace(' ', '').replace('-', '')
            cursor.execute("SELECT * FROM users WHERE phone = ? OR phone = ?", (phone, '+' + phone))
            user = cursor.fetchone()
            return tuple(user) if user else None
    except Exception as e:
        logger.error(f"get_user_by_phone error: {e}")
        return None


def update_user_phone(user_id, phone):
    """Foydalanuvchi telefon raqamini yangilash"""
    try:
        with get_db_transaction() as (conn, cursor):
            # Telefon raqamni normalizatsiya qilish
            phone = phone.replace(' ', '').replace('-', '')
            if not phone.startswith('+'):
                phone = '+' + phone
            cursor.execute('UPDATE users SET phone = ? WHERE user_id = ?', (phone, user_id))
        return True
    except Exception as e:
        logger.error(f"update_user_phone error: {e}")
        return False


def update_balance(user_id, amount):
    """
    Balansni yangilash — atomic. Ayirishda balans yetarli bo'lmasa False qaytaradi
    (balans manfiyga tushmaydi, race condition'dan himoyalangan).
    """
    try:
        with get_db_transaction() as (conn, cursor):
            # Foydalanuvchi mavjudligini tekshirish
            cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
            exists = cursor.fetchone()

            # Foydalanuvchi yo'q bo'lsa — yaratish (kredit bo'lsa)
            if exists is None:
                if amount < 0:
                    logger.warning(f"update_balance: user {user_id} yo'q, ayirish rad etildi")
                    return False
                cursor.execute('''
                    INSERT INTO users (user_id, balance, created_at)
                    VALUES (?, ?, datetime('now'))
                ''', (user_id, amount))
                logger.info(f"Created new user {user_id} with balance {amount}")
                return True

            if amount < 0:
                # Atomic decrement: faqat balans >= |amount| bo'lsa yangilanadi
                cursor.execute(
                    '''
                    UPDATE users SET balance = balance + ?
                    WHERE user_id = ? AND balance + ? >= 0
                    ''',
                    (amount, user_id, amount),
                )
                if cursor.rowcount == 0:
                    logger.warning(f"Insufficient balance for user {user_id} (need {-amount})")
                    return False
            else:
                cursor.execute(
                    'UPDATE users SET balance = balance + ? WHERE user_id = ?',
                    (amount, user_id),
                )
        return True
    except Exception as e:
        logger.error(f"update_balance error: {e}")
        return False


def get_balance(user_id):
    """Balansni olish"""
    try:
        with get_db_connection() as (conn, cursor):
            cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            return result[0] if result else 0
    except Exception as e:
        logger.error(f"get_balance error: {e}")
        return 0


def add_order(user_id, service_type, link, quantity, price):
    """Yangi buyurtma qo'shish - transaction bilan"""
    try:
        with get_db_transaction() as (conn, cursor):
            cursor.execute('''
                INSERT INTO orders (user_id, service_type, link, quantity, price, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, service_type, link, quantity, price, 'pending', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"add_order error: {e}")
        return None


def create_order_with_balance_deduction(user_id, service_type, link, quantity, price):
    """
    Buyurtma yaratish va balansdan yechish - ATOMIC TRANSACTION
    Race condition'ni oldini oladi - balans va buyurtma birgalikda
    """
    try:
        with get_db_transaction() as (conn, cursor):
            # 1. Balansni tekshirish
            cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            current_balance = result[0] if result else 0
            
            if current_balance < price:
                logger.warning(f"Insufficient balance: user={user_id}, balance={current_balance}, price={price}")
                return None, "insufficient_balance"
            
            # 2. Balansdan yechish
            cursor.execute('''
                UPDATE users SET balance = balance - ? WHERE user_id = ?
            ''', (price, user_id))
            
            # 3. Buyurtma yaratish
            cursor.execute('''
                INSERT INTO orders (user_id, service_type, link, quantity, price, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, service_type, link, quantity, price, 'pending', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            
            order_id = cursor.lastrowid
            logger.info(f"Order created: id={order_id}, user={user_id}, price={price}")
            return order_id, "success"
            
    except Exception as e:
        logger.error(f"create_order_with_balance_deduction error: {e}")
        return None, str(e)


def get_user_orders(user_id):
    """Foydalanuvchi buyurtmalarini olish"""
    try:
        with get_db_connection() as (conn, cursor):
            cursor.execute('''
                SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 10
            ''', (user_id,))
            orders = cursor.fetchall()
            return [tuple(order) for order in orders]
    except Exception as e:
        logger.error(f"get_user_orders error: {e}")
        return []


def add_payment(user_id, amount, method):
    """Yangi to'lov qo'shish"""
    try:
        with get_db_transaction() as (conn, cursor):
            cursor.execute('''
                INSERT INTO payments (user_id, amount, method, created_at)
                VALUES (?, ?, ?, ?)
            ''', (user_id, amount, method, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"add_payment error: {e}")
        return None


def get_referral_stats(user_id):
    """Referal statistikasini olish"""
    try:
        with get_db_connection() as (conn, cursor):
            cursor.execute('''
                SELECT referral_count, referral_earnings FROM users WHERE user_id = ?
            ''', (user_id,))
            result = cursor.fetchone()
            return (result[0], result[1]) if result else (0, 0)
    except Exception as e:
        logger.error(f"get_referral_stats error: {e}")
        return (0, 0)

def get_all_users():
    """Barcha foydalanuvchilarni olish"""
    try:
        with get_db_connection() as (conn, cursor):
            cursor.execute("SELECT user_id FROM users")
            users = cursor.fetchall()
            return [user[0] for user in users]
    except Exception as e:
        logger.error(f"get_all_users error: {e}")
        return []


def update_order_status(order_id, status):
    """Buyurtma holatini yangilash"""
    try:
        with get_db_transaction() as (conn, cursor):
            cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
            return True
    except Exception as e:
        logger.error(f"update_order_status error (order_id={order_id}): {e}")
        return False


def update_order_api_id(order_id, api_order_id, panel_name=None):
    """Buyurtmaga API order ID va panel nomi qo'shish"""
    try:
        with get_db_transaction() as (conn, cursor):
            if panel_name:
                cursor.execute("UPDATE orders SET api_order_id = ?, panel_name = ? WHERE id = ?", (api_order_id, panel_name, order_id))
            else:
                cursor.execute("UPDATE orders SET api_order_id = ? WHERE id = ?", (api_order_id, order_id))
            return True
    except Exception as e:
        logger.error(f"update_order_api_id error (order_id={order_id}): {e}")
        return False


def get_pending_orders():
    """Kutilayotgan buyurtmalarni olish"""
    try:
        with get_db_connection() as (conn, cursor):
            cursor.execute("""
                SELECT id, api_order_id, user_id, panel_name 
                FROM orders 
                WHERE status IN ('pending', 'processing', 'In progress') 
                AND api_order_id IS NOT NULL
            """)
            orders = cursor.fetchall()
            return orders
    except Exception as e:
        logger.error(f"get_pending_orders error: {e}")
        return []


def get_orders_by_status(status):
    """Status bo'yicha buyurtmalarni olish"""
    try:
        with get_db_connection() as (conn, cursor):
            cursor.execute("""
                SELECT id, user_id, service_type, quantity, price, status, created_at 
                FROM orders 
                WHERE status = ? 
                ORDER BY created_at DESC LIMIT 20
            """, (status,))
            orders = cursor.fetchall()
            return orders
    except Exception as e:
        logger.error(f"get_orders_by_status error: {e}")
        return []


def get_user_orders_admin(user_id):
    """Admin uchun foydalanuvchi buyurtmalari"""
    try:
        with get_db_connection() as (conn, cursor):
            cursor.execute("""
                SELECT id, service_type, quantity, price, status, created_at 
                FROM orders WHERE user_id = ? 
                ORDER BY created_at DESC LIMIT 20
            """, (user_id,))
            orders = cursor.fetchall()
            return orders
    except Exception as e:
        logger.error(f"get_user_orders_admin error: {e}")
        return []


def get_user_payments_admin(user_id):
    """Admin uchun foydalanuvchi to'lovlari"""
    try:
        with get_db_connection() as (conn, cursor):
            cursor.execute("""
                SELECT id, amount, method, status, created_at 
                FROM payments WHERE user_id = ? 
                ORDER BY created_at DESC LIMIT 20
            """, (user_id,))
            payments = cursor.fetchall()
            return payments
    except Exception as e:
        logger.error(f"get_user_payments_admin error: {e}")
        return []


def get_payments_by_status(status):
    """Status bo'yicha to'lovlarni olish"""
    try:
        with get_db_connection() as (conn, cursor):
            cursor.execute("""
                SELECT id, user_id, amount, method, status, created_at 
                FROM payments WHERE status = ? 
                ORDER BY created_at DESC LIMIT 20
            """, (status,))
            payments = cursor.fetchall()
            return payments
    except Exception as e:
        logger.error(f"get_payments_by_status error: {e}")
        return []


def approve_payment(payment_id):
    """To'lovni tasdiqlash va balansga qo'shish - ATOMIC TRANSACTION"""
    try:
        with get_db_transaction() as (conn, cursor):
            cursor.execute("SELECT user_id, amount, status FROM payments WHERE id = ?", (payment_id,))
            payment = cursor.fetchone()
            
            if not payment:
                return False, "To'lov topilmadi"
            
            user_id, amount, status = payment
            
            if status == 'approved':
                return False, "Bu to'lov allaqachon tasdiqlangan"
            
            # To'lovni tasdiqlash va balansga qo'shish - bir tranzaksiyada
            cursor.execute("UPDATE payments SET status = 'approved' WHERE id = ?", (payment_id,))
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            
            logger.info(f"Payment approved: payment_id={payment_id}, user_id={user_id}, amount={amount}")
            return True, user_id
    except Exception as e:
        logger.error(f"approve_payment error (payment_id={payment_id}): {e}")
        return False, f"Xatolik: {str(e)}"


def reject_payment(payment_id):
    """To'lovni rad etish"""
    try:
        with get_db_transaction() as (conn, cursor):
            cursor.execute("UPDATE payments SET status = 'rejected' WHERE id = ?", (payment_id,))
            cursor.execute("SELECT user_id FROM payments WHERE id = ?", (payment_id,))
            result = cursor.fetchone()
            logger.info(f"Payment rejected: payment_id={payment_id}")
            return result[0] if result else None
    except Exception as e:
        logger.error(f"reject_payment error (payment_id={payment_id}): {e}")
        return None


def cancel_order_and_refund(order_id):
    """Buyurtmani bekor qilish va pul qaytarish - ATOMIC TRANSACTION"""
    try:
        with get_db_transaction() as (conn, cursor):
            cursor.execute("SELECT user_id, price, status FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()
            
            if not order:
                return False, "Buyurtma topilmadi", None
            
            user_id, price, status = order
            
            if status == 'canceled':
                return False, "Bu buyurtma allaqachon bekor qilingan", None
            
            # Buyurtmani bekor qilish va pulni qaytarish - bir tranzaksiyada
            cursor.execute("UPDATE orders SET status = 'canceled' WHERE id = ?", (order_id,))
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (price, user_id))
            
            logger.info(f"Order canceled and refunded: order_id={order_id}, user_id={user_id}, refund={price}")
            return True, price, user_id
    except Exception as e:
        logger.error(f"cancel_order_and_refund error (order_id={order_id}): {e}")
        return False, f"Xatolik: {str(e)}", None


def get_banned_users():
    """Bloklangan foydalanuvchilarni olish"""
    try:
        with get_db_connection() as (conn, cursor):
            cursor.execute("SELECT user_id, username, full_name, created_at FROM users WHERE is_banned = 1")
            users = cursor.fetchall()
            return users
    except Exception as e:
        logger.error(f"get_banned_users error: {e}")
        return []


def get_users_with_balance():
    """Balansi bor foydalanuvchilar"""
    try:
        with get_db_connection() as (conn, cursor):
            cursor.execute("SELECT user_id FROM users WHERE balance > 0")
            users = cursor.fetchall()
            return [u[0] for u in users]
    except Exception as e:
        logger.error(f"get_users_with_balance error: {e}")
        return []


def get_users_with_orders():
    """Buyurtma bergan foydalanuvchilar"""
    try:
        with get_db_connection() as (conn, cursor):
            cursor.execute("SELECT DISTINCT user_id FROM orders")
            users = cursor.fetchall()
            return [u[0] for u in users]
    except Exception as e:
        logger.error(f"get_users_with_orders error: {e}")
        return []


def get_top_orders_users(limit=15):
    """Eng ko'p buyurtma bergan foydalanuvchilar"""
    try:
        with get_db_connection() as (conn, cursor):
            cursor.execute("""
                SELECT u.user_id, u.username, u.full_name, COUNT(o.id) as order_count, SUM(o.price) as total_spent
                FROM users u
                LEFT JOIN orders o ON u.user_id = o.user_id
                GROUP BY u.user_id
                ORDER BY order_count DESC
                LIMIT ?
            """, (limit,))
            users = cursor.fetchall()
            return users
    except Exception as e:
        logger.error(f"get_top_orders_users error: {e}")
        return []


# ==================== PREMIUM OBUNA FUNKSIYALARI ====================

def add_premium_subscription(user_id, plan_type, months, price):
    """Premium obuna qo'shish"""
    from datetime import timedelta
    try:
        with get_db_transaction() as (conn, cursor):
            now = datetime.now()
            start_date = now.strftime("%Y-%m-%d %H:%M:%S")
            end_date = (now + timedelta(days=months * 30)).strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute('''
                INSERT INTO premium_subscriptions (user_id, plan_type, months, price, start_date, end_date, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'active', ?)
            ''', (user_id, plan_type, months, price, start_date, end_date, start_date))
            
            subscription_id = cursor.lastrowid
            logger.info(f"Premium subscription added: user_id={user_id}, plan={plan_type}, months={months}")
            return subscription_id
    except Exception as e:
        logger.error(f"add_premium_subscription error: {e}")
        return None


def get_user_premium(user_id):
    """Foydalanuvchining aktiv premium obunasini olish"""
    try:
        with get_db_connection() as (conn, cursor):
            cursor.execute('''
                SELECT id, plan_type, months, price, start_date, end_date, status
                FROM premium_subscriptions
                WHERE user_id = ? AND status = 'active' AND end_date > datetime('now')
                ORDER BY end_date DESC
                LIMIT 1
            ''', (user_id,))
            result = cursor.fetchone()
            return result
    except Exception as e:
        logger.error(f"get_user_premium error: {e}")
        return None


def check_premium_status(user_id):
    """Foydalanuvchi premium ekanligini tekshirish"""
    premium = get_user_premium(user_id)
    return premium is not None


def get_premium_remaining_days(user_id):
    """Premium kunlar qolganini hisoblash"""
    try:
        with get_db_connection() as (conn, cursor):
            cursor.execute('''
                SELECT end_date FROM premium_subscriptions
                WHERE user_id = ? AND status = 'active' AND end_date > datetime('now')
                ORDER BY end_date DESC
                LIMIT 1
            ''', (user_id,))
            result = cursor.fetchone()
            
            if result:
                from datetime import datetime as dt
                end_date = dt.strptime(result[0], "%Y-%m-%d %H:%M:%S")
                remaining = (end_date - dt.now()).days
                return max(0, remaining)
            return 0
    except Exception as e:
        logger.error(f"get_premium_remaining_days error: {e}")
        return 0


def get_all_premium_users():
    """Barcha premium foydalanuvchilarni olish"""
    try:
        with get_db_connection() as (conn, cursor):
            cursor.execute('''
                SELECT DISTINCT user_id FROM premium_subscriptions
                WHERE status = 'active' AND end_date > datetime('now')
            ''')
            users = cursor.fetchall()
            return [u[0] for u in users]
    except Exception as e:
        logger.error(f"get_all_premium_users error: {e}")
        return []


def get_premium_stats():
    """Premium statistikasi"""
    try:
        with get_db_connection() as (conn, cursor):
            # Jami premium sotilgan
            cursor.execute("SELECT COUNT(*) FROM premium_subscriptions")
            total_sold = cursor.fetchone()[0]
            
            # Aktiv premium
            cursor.execute('''
                SELECT COUNT(DISTINCT user_id) FROM premium_subscriptions
                WHERE status = 'active' AND end_date > datetime('now')
            ''')
            active_count = cursor.fetchone()[0]
            
            # Jami daromad
            cursor.execute("SELECT SUM(price) FROM premium_subscriptions")
            total_revenue = cursor.fetchone()[0] or 0
            
            return {
                'total_sold': total_sold,
                'active_count': active_count,
                'total_revenue': total_revenue
            }
    except Exception as e:
        logger.error(f"get_premium_stats error: {e}")
        return {'total_sold': 0, 'active_count': 0, 'total_revenue': 0}


# ==================== PREMIUM SO'ROVLAR FUNKSIYALARI ====================

def add_premium_request(user_id, phone, months, price):
    """Premium so'rov qo'shish"""
    try:
        with get_db_transaction() as (conn, cursor):
            cursor.execute('''
                INSERT INTO premium_requests (user_id, phone, months, price, status, created_at)
                VALUES (?, ?, ?, ?, 'pending', ?)
            ''', (user_id, phone, months, price, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            
            request_id = cursor.lastrowid
            logger.info(f"Premium request added: user_id={user_id}, months={months}, price={price}")
            return request_id
    except Exception as e:
        logger.error(f"add_premium_request error: {e}")
        return None


def get_premium_request(request_id):
    """Premium so'rovni olish"""
    try:
        with get_db_connection() as (conn, cursor):
            cursor.execute("SELECT * FROM premium_requests WHERE id = ?", (request_id,))
            result = cursor.fetchone()
            return result
    except Exception as e:
        logger.error(f"get_premium_request error: {e}")
        return None


def update_premium_request_status(request_id, status, admin_message_id=None):
    """Premium so'rov holatini yangilash"""
    try:
        with get_db_transaction() as (conn, cursor):
            if admin_message_id:
                cursor.execute('''
                    UPDATE premium_requests SET status = ?, admin_message_id = ?, processed_at = ?
                    WHERE id = ?
                ''', (status, admin_message_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), request_id))
            else:
                cursor.execute('''
                    UPDATE premium_requests SET status = ?, processed_at = ?
                    WHERE id = ?
                ''', (status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), request_id))
            
            logger.info(f"Premium request status updated: request_id={request_id}, status={status}")
            return True
    except Exception as e:
        logger.error(f"update_premium_request_status error: {e}")
        return False


# ==================== CLICK TO'LOVLAR FUNKSIYALARI ====================

def add_click_payment(user_id, amount):
    """Yangi Click to'lov yaratish"""
    try:
        with get_db_transaction() as (conn, cursor):
            cursor.execute('''
                INSERT INTO click_payments (user_id, amount, status, created_at)
                VALUES (?, ?, 'pending', ?)
            ''', (user_id, amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"add_click_payment error: {e}")
        return None


def get_click_payment(payment_id):
    """Click to'lovni olish"""
    try:
        with get_db_connection() as (conn, cursor):
            cursor.execute("SELECT * FROM click_payments WHERE id = ?", (payment_id,))
            result = cursor.fetchone()
            if result:
                return dict(result)
            return None
    except Exception as e:
        logger.error(f"get_click_payment error: {e}")
        return None


def update_click_payment_status(payment_id, status, click_trans_id=None, click_paydoc_id=None, error_code=None):
    """Click to'lov holatini yangilash"""
    try:
        with get_db_transaction() as (conn, cursor):
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
            return True
    except Exception as e:
        logger.error(f"update_click_payment_status error: {e}")
        return False


def get_user_click_payments(user_id, limit=20):
    """Foydalanuvchining Click to'lovlarini olish"""
    try:
        with get_db_connection() as (conn, cursor):
            cursor.execute('''
                SELECT * FROM click_payments 
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (user_id, limit))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"get_user_click_payments error: {e}")
        return []


def get_pending_click_payments():
    """Kutilayotgan Click to'lovlarni olish (admin uchun)"""
    try:
        with get_db_connection() as (conn, cursor):
            cursor.execute('''
                SELECT cp.*, u.username, u.full_name 
                FROM click_payments cp
                LEFT JOIN users u ON cp.user_id = u.user_id
                WHERE cp.status = 'pending' OR cp.status = 'preparing'
                ORDER BY cp.created_at DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"get_pending_click_payments error: {e}")
        return []
        return False


def get_pending_premium_requests():
    """Kutilayotgan premium so'rovlarni olish"""
    try:
        with get_db_connection() as (conn, cursor):
            cursor.execute('''
                SELECT pr.*, u.full_name, u.username 
                FROM premium_requests pr
                LEFT JOIN users u ON pr.user_id = u.user_id
                WHERE pr.status = 'pending'
                ORDER BY pr.created_at DESC
            ''')
            results = cursor.fetchall()
            return results
    except Exception as e:
        logger.error(f"get_pending_premium_requests error: {e}")
        return []
