import aiosqlite
from config import DATABASE_PATH
from typing import List, Optional, Dict

class Database:
    def __init__(self):
        self.db_path = DATABASE_PATH
    
    async def init_db(self):
        """Инициализация базы данных и создание таблиц"""
        async with aiosqlite.connect(self.db_path) as db:
            # Таблица пользователей
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    role TEXT DEFAULT 'user',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица комнат
            await db.execute('''
                CREATE TABLE IF NOT EXISTS rooms (
                    room_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_name TEXT NOT NULL,
                    customer_id INTEGER,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (customer_id) REFERENCES users(user_id),
                    FOREIGN KEY (created_by) REFERENCES users(user_id)
                )
            ''')
            
            # Таблица доступа к комнатам (кто может видеть и писать в комнате)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS room_access (
                    access_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER,
                    user_id INTEGER,
                    access_type TEXT DEFAULT 'developer',
                    FOREIGN KEY (room_id) REFERENCES rooms(room_id),
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    UNIQUE(room_id, user_id)
                )
            ''')
            
            # Таблица сообщений (для истории)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER,
                    sender_id INTEGER,
                    message_text TEXT,
                    is_from_customer BOOLEAN,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (room_id) REFERENCES rooms(room_id),
                    FOREIGN KEY (sender_id) REFERENCES users(user_id)
                )
            ''')
            
            # Таблица чатов (диалоги с пользователями до создания комнаты)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS chats (
                    chat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    unread_count INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    UNIQUE(user_id)
                )
            ''')
            
            # Таблица сообщений в чатах
            await db.execute('''
                CREATE TABLE IF NOT EXISTS chat_messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER,
                    sender_id INTEGER,
                    message_text TEXT,
                    is_from_user BOOLEAN,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (chat_id) REFERENCES chats(chat_id),
                    FOREIGN KEY (sender_id) REFERENCES users(user_id)
                )
            ''')
            
            # Таблица заказчиков с пометками
            await db.execute('''
                CREATE TABLE IF NOT EXISTS customers (
                    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    notes TEXT,
                    status TEXT DEFAULT 'new',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    UNIQUE(user_id)
                )
            ''')
            
            # Таблица настроек уведомлений по комнатам
            await db.execute('''
                CREATE TABLE IF NOT EXISTS room_notifications (
                    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    room_id INTEGER,
                    enabled BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (room_id) REFERENCES rooms(room_id),
                    UNIQUE(user_id, room_id)
                )
            ''')
            
            # Таблица отзывов
            await db.execute('''
                CREATE TABLE IF NOT EXISTS reviews (
                    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    room_id INTEGER,
                    review_text TEXT NOT NULL,
                    admin_reply TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (room_id) REFERENCES rooms(room_id)
                )
            ''')
            
            # Таблица истории заказов (удаленные/закрытые комнаты)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS order_history (
                    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER,
                    room_name TEXT NOT NULL,
                    customer_id INTEGER,
                    created_by INTEGER,
                    closed_by INTEGER,
                    closed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    room_created_at TIMESTAMP,
                    FOREIGN KEY (customer_id) REFERENCES users(user_id),
                    FOREIGN KEY (created_by) REFERENCES users(user_id),
                    FOREIGN KEY (closed_by) REFERENCES users(user_id)
                )
            ''')
            
            # Добавляем поле status в таблицу rooms для отслеживания статуса (active/closed)
            try:
                await db.execute('ALTER TABLE rooms ADD COLUMN status TEXT DEFAULT "active"')
            except:
                pass  # Поле уже существует
            
            await db.commit()
    
    async def add_user(self, user_id: int, username: str = None, full_name: str = None, role: str = 'user'):
        """Добавить пользователя в базу"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR REPLACE INTO users (user_id, username, full_name, role)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, full_name, role))
            await db.commit()
    
    async def get_user_role(self, user_id: int) -> Optional[str]:
        """Получить роль пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT role FROM users WHERE user_id = ?', (user_id,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None
    
    async def is_admin(self, user_id: int) -> bool:
        """Проверить, является ли пользователь администратором"""
        role = await self.get_user_role(user_id)
        return role == 'admin'
    
    async def create_room(self, room_name: str, created_by: int, customer_id: int = None) -> int:
        """Создать новую комнату"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                INSERT INTO rooms (room_name, customer_id, created_by)
                VALUES (?, ?, ?)
            ''', (room_name, customer_id, created_by))
            room_id = cursor.lastrowid
            
            # Автоматически даем доступ заказчику, если указан
            if customer_id:
                await db.execute('''
                    INSERT INTO room_access (room_id, user_id, access_type)
                    VALUES (?, ?, 'customer')
                ''', (room_id, customer_id))
            
            # Автоматически даем доступ создателю (админу)
            await db.execute('''
                INSERT INTO room_access (room_id, user_id, access_type)
                VALUES (?, ?, 'developer')
            ''', (room_id, created_by))
            
            await db.commit()
            return room_id
    
    async def get_room(self, room_id: int) -> Optional[Dict]:
        """Получить информацию о комнате"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT room_id, room_name, customer_id, created_by, created_at
                FROM rooms WHERE room_id = ?
            ''', (room_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        'room_id': row[0],
                        'room_name': row[1],
                        'customer_id': row[2],
                        'created_by': row[3],
                        'created_at': row[4]
                    }
                return None
    
    async def get_user_rooms(self, user_id: int, is_admin: bool = False) -> List[Dict]:
        """Получить все комнаты, к которым у пользователя есть доступ"""
        async with aiosqlite.connect(self.db_path) as db:
            if is_admin:
                # Администраторы видят все комнаты
                async with db.execute('''
                    SELECT r.room_id, r.room_name, r.customer_id, 
                           COALESCE(ra.access_type, 'admin') as access_type
                    FROM rooms r
                    LEFT JOIN room_access ra ON r.room_id = ra.room_id AND ra.user_id = ?
                    ORDER BY r.created_at DESC
                ''', (user_id,)) as cursor:
                    rows = await cursor.fetchall()
                    return [{
                        'room_id': row[0],
                        'room_name': row[1],
                        'customer_id': row[2],
                        'access_type': row[3]
                    } for row in rows]
            else:
                async with db.execute('''
                    SELECT r.room_id, r.room_name, r.customer_id, ra.access_type
                    FROM rooms r
                    JOIN room_access ra ON r.room_id = ra.room_id
                    WHERE ra.user_id = ?
                    ORDER BY r.created_at DESC
                ''', (user_id,)) as cursor:
                    rows = await cursor.fetchall()
                    return [{
                        'room_id': row[0],
                        'room_name': row[1],
                        'customer_id': row[2],
                        'access_type': row[3]
                    } for row in rows]
    
    async def add_room_access(self, room_id: int, user_id: int, access_type: str = 'developer'):
        """Добавить доступ пользователю к комнате"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR REPLACE INTO room_access (room_id, user_id, access_type)
                VALUES (?, ?, ?)
            ''', (room_id, user_id, access_type))
            await db.commit()
    
    async def remove_room_access(self, room_id: int, user_id: int):
        """Удалить доступ пользователя к комнате"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                DELETE FROM room_access WHERE room_id = ? AND user_id = ?
            ''', (room_id, user_id))
            await db.commit()
    
    async def get_room_access(self, room_id: int, user_id: int) -> Optional[Dict]:
        """Получить доступ пользователя к комнате"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT access_id, room_id, user_id, access_type
                FROM room_access
                WHERE room_id = ? AND user_id = ?
            ''', (room_id, user_id)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        'access_id': row[0],
                        'room_id': row[1],
                        'user_id': row[2],
                        'access_type': row[3]
                    }
                return None
    
    async def get_room_members(self, room_id: int) -> List[Dict]:
        """Получить всех участников комнаты"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT u.user_id, u.username, u.full_name, ra.access_type
                FROM room_access ra
                JOIN users u ON ra.user_id = u.user_id
                WHERE ra.room_id = ?
            ''', (room_id,)) as cursor:
                rows = await cursor.fetchall()
                return [{
                    'user_id': row[0],
                    'username': row[1],
                    'full_name': row[2],
                    'access_type': row[3]
                } for row in rows]
    
    async def get_room_customer(self, room_id: int) -> Optional[int]:
        """Получить ID заказчика комнаты"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT customer_id FROM rooms WHERE room_id = ?', (room_id,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None
    
    async def save_message(self, room_id: int, sender_id: int, message_text: str, is_from_customer: bool):
        """Сохранить сообщение в историю"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO messages (room_id, sender_id, message_text, is_from_customer)
                VALUES (?, ?, ?, ?)
            ''', (room_id, sender_id, message_text, is_from_customer))
            await db.commit()
    
    async def get_room_messages(self, room_id: int, limit: int = 50) -> List[Dict]:
        """Получить историю сообщений комнаты"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT message_id, sender_id, message_text, is_from_customer, created_at
                FROM messages
                WHERE room_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (room_id, limit)) as cursor:
                rows = await cursor.fetchall()
                return [{
                    'message_id': row[0],
                    'sender_id': row[1],
                    'message_text': row[2],
                    'is_from_customer': row[3],
                    'created_at': row[4]
                } for row in rows]
    
    async def get_all_rooms(self) -> List[Dict]:
        """Получить все комнаты (для администраторов)"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT room_id, room_name, customer_id, created_by, created_at
                FROM rooms
                ORDER BY created_at DESC
            ''') as cursor:
                rows = await cursor.fetchall()
                return [{
                    'room_id': row[0],
                    'room_name': row[1],
                    'customer_id': row[2],
                    'created_by': row[3],
                    'created_at': row[4]
                } for row in rows]
    
    async def delete_room(self, room_id: int):
        """Удалить комнату и все связанные данные"""
        async with aiosqlite.connect(self.db_path) as db:
            # Удаляем уведомления
            await db.execute('DELETE FROM room_notifications WHERE room_id = ?', (room_id,))
            # Удаляем доступы к комнате
            await db.execute('DELETE FROM room_access WHERE room_id = ?', (room_id,))
            # Удаляем сообщения комнаты
            await db.execute('DELETE FROM messages WHERE room_id = ?', (room_id,))
            # Удаляем саму комнату
            await db.execute('DELETE FROM rooms WHERE room_id = ?', (room_id,))
            await db.commit()
    
    async def update_room_name(self, room_id: int, new_name: str):
        """Обновить название комнаты"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE rooms SET room_name = ? WHERE room_id = ?
            ''', (new_name, room_id))
            await db.commit()
    
    async def update_user_role_in_room(self, room_id: int, user_id: int, new_role: str):
        """Изменить роль пользователя в комнате"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE room_access SET access_type = ? WHERE room_id = ? AND user_id = ?
            ''', (new_role, room_id, user_id))
            await db.commit()
    
    # Методы для работы с чатами
    async def get_or_create_chat(self, user_id: int) -> int:
        """Получить или создать чат с пользователем"""
        async with aiosqlite.connect(self.db_path) as db:
            # Проверяем, есть ли чат
            async with db.execute('SELECT chat_id FROM chats WHERE user_id = ?', (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return row[0]
            
            # Создаем новый чат
            cursor = await db.execute('''
                INSERT INTO chats (user_id, last_message_at, unread_count)
                VALUES (?, CURRENT_TIMESTAMP, 0)
            ''', (user_id,))
            await db.commit()
            return cursor.lastrowid
    
    async def save_chat_message(self, chat_id: int, sender_id: int, message_text: str, is_from_user: bool):
        """Сохранить сообщение в чат"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO chat_messages (chat_id, sender_id, message_text, is_from_user)
                VALUES (?, ?, ?, ?)
            ''', (chat_id, sender_id, message_text, is_from_user))
            
            # Обновляем время последнего сообщения и счетчик непрочитанных
            if is_from_user:
                await db.execute('''
                    UPDATE chats 
                    SET last_message_at = CURRENT_TIMESTAMP, 
                        unread_count = unread_count + 1
                    WHERE chat_id = ?
                ''', (chat_id,))
            
            await db.commit()
    
    async def get_all_chats(self) -> List[Dict]:
        """Получить все чаты (для администраторов)"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT c.chat_id, c.user_id, c.last_message_at, c.unread_count,
                       u.username, u.full_name
                FROM chats c
                JOIN users u ON c.user_id = u.user_id
                ORDER BY c.last_message_at DESC
            ''') as cursor:
                rows = await cursor.fetchall()
                return [{
                    'chat_id': row[0],
                    'user_id': row[1],
                    'last_message_at': row[2],
                    'unread_count': row[3],
                    'username': row[4],
                    'full_name': row[5]
                } for row in rows]
    
    async def get_chat_messages(self, chat_id: int, limit: int = 50) -> List[Dict]:
        """Получить сообщения чата"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT message_id, sender_id, message_text, is_from_user, created_at
                FROM chat_messages
                WHERE chat_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (chat_id, limit)) as cursor:
                rows = await cursor.fetchall()
                return [{
                    'message_id': row[0],
                    'sender_id': row[1],
                    'message_text': row[2],
                    'is_from_user': row[3],
                    'created_at': row[4]
                } for row in rows]
    
    async def mark_chat_as_read(self, chat_id: int):
        """Отметить чат как прочитанный"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE chats SET unread_count = 0 WHERE chat_id = ?', (chat_id,))
            await db.commit()
    
    async def get_chat_by_user_id(self, user_id: int) -> Optional[Dict]:
        """Получить чат по ID пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT chat_id, user_id, last_message_at, unread_count
                FROM chats WHERE user_id = ?
            ''', (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        'chat_id': row[0],
                        'user_id': row[1],
                        'last_message_at': row[2],
                        'unread_count': row[3]
                    }
                return None
    
    async def get_chat_by_chat_id(self, chat_id: int) -> Optional[Dict]:
        """Получить чат по ID чата"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT chat_id, user_id, last_message_at, unread_count
                FROM chats WHERE chat_id = ?
            ''', (chat_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        'chat_id': row[0],
                        'user_id': row[1],
                        'last_message_at': row[2],
                        'unread_count': row[3]
                    }
                return None
    
    # Методы для работы с заказчиками
    async def add_or_update_customer(self, user_id: int, notes: str = None):
        """Добавить или обновить заказчика с пометками"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR REPLACE INTO customers (user_id, notes, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, notes))
            await db.commit()
    
    async def update_customer_notes(self, user_id: int, notes: str):
        """Обновить пометки о заказчике"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE customers 
                SET notes = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (notes, user_id))
            await db.commit()
    
    async def remove_customer(self, user_id: int):
        """Удалить пользователя из базы заказчиков"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('DELETE FROM customers WHERE user_id = ?', (user_id,))
            await db.commit()
    
    async def get_customer_info(self, user_id: int) -> Optional[Dict]:
        """Получить информацию о заказчике"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT customer_id, user_id, notes, status, created_at, updated_at
                FROM customers WHERE user_id = ?
            ''', (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        'customer_id': row[0],
                        'user_id': row[1],
                        'notes': row[2],
                        'status': row[3],
                        'created_at': row[4],
                        'updated_at': row[5]
                    }
                return None
    
    async def get_all_customers(self) -> List[Dict]:
        """Получить всех заказчиков с пометками (исключая админов и разработчиков)"""
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем всех пользователей из таблицы customers, исключая админов и разработчиков
            async with db.execute('''
                SELECT u.user_id, u.username, u.full_name, u.created_at, u.role,
                       c.customer_id, c.notes, c.status, c.created_at as customer_created_at, c.updated_at
                FROM customers c
                JOIN users u ON c.user_id = u.user_id
                WHERE u.role != 'admin' AND u.role != 'developer'
                ORDER BY COALESCE(c.updated_at, u.created_at) DESC
            ''') as cursor:
                rows = await cursor.fetchall()
                result = []
                for row in rows:
                    # row[0] = user_id, row[1] = username, row[2] = full_name, row[3] = created_at, row[4] = role
                    # row[5] = customer_id, row[6] = notes, row[7] = status, row[8] = customer_created_at, row[9] = updated_at
                    result.append({
                        'customer_id': row[5],
                        'user_id': row[0],
                        'notes': row[6],
                        'status': row[7] if row[7] else 'new',
                        'created_at': row[8] if row[8] else row[3],
                        'updated_at': row[9] if row[9] else row[3],
                        'username': row[1],
                        'full_name': row[2],
                        'role': row[4]
                    })
                return result
    
    # Методы для работы с уведомлениями
    async def set_room_notification(self, user_id: int, room_id: int, enabled: bool):
        """Установить настройку уведомлений для пользователя в комнате"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR REPLACE INTO room_notifications (user_id, room_id, enabled)
                VALUES (?, ?, ?)
            ''', (user_id, room_id, 1 if enabled else 0))
            await db.commit()
    
    async def get_room_notification(self, user_id: int, room_id: int) -> bool:
        """Получить настройку уведомлений для пользователя в комнате (по умолчанию True)"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT enabled FROM room_notifications 
                WHERE user_id = ? AND room_id = ?
            ''', (user_id, room_id)) as cursor:
                row = await cursor.fetchone()
                if row is not None:
                    return bool(row[0])
                # По умолчанию уведомления включены
                return True
    
    async def get_user_notification_rooms(self, user_id: int) -> List[Dict]:
        """Получить все комнаты с настройками уведомлений для пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT r.room_id, r.room_name, r.customer_id,
                       COALESCE(rn.enabled, 1) as enabled
                FROM rooms r
                LEFT JOIN room_notifications rn ON r.room_id = rn.room_id AND rn.user_id = ?
                ORDER BY r.created_at DESC
            ''', (user_id,)) as cursor:
                rows = await cursor.fetchall()
                return [{
                    'room_id': row[0],
                    'room_name': row[1],
                    'customer_id': row[2],
                    'enabled': bool(row[3])
                } for row in rows]
    
    async def get_room_users_with_notifications(self, room_id: int, exclude_user_id: int = None) -> List[int]:
        """Получить список пользователей, которым нужно отправить уведомление о новом сообщении в комнате"""
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем всех пользователей с доступом к комнате, у которых включены уведомления
            query = '''
                SELECT DISTINCT ra.user_id
                FROM room_access ra
                LEFT JOIN room_notifications rn ON ra.room_id = rn.room_id AND ra.user_id = rn.user_id
                WHERE ra.room_id = ? 
                AND (rn.enabled IS NULL OR rn.enabled = 1)
            '''
            params = [room_id]
            
            if exclude_user_id:
                query += ' AND ra.user_id != ?'
                params.append(exclude_user_id)
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
    
    # Методы для работы с ролями пользователей
    async def get_users_by_role(self, role: str) -> List[Dict]:
        """Получить всех пользователей с определенной ролью"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT user_id, username, full_name, role, created_at
                FROM users
                WHERE role = ?
                ORDER BY created_at DESC
            ''', (role,)) as cursor:
                rows = await cursor.fetchall()
                return [{
                    'user_id': row[0],
                    'username': row[1],
                    'full_name': row[2],
                    'role': row[3],
                    'created_at': row[4]
                } for row in rows]
    
    async def update_user_role(self, user_id: int, new_role: str):
        """Изменить роль пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE users SET role = ? WHERE user_id = ?
            ''', (new_role, user_id))
            await db.commit()
    
    async def get_all_users(self) -> List[Dict]:
        """Получить всех пользователей"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT user_id, username, full_name, role, created_at
                FROM users
                ORDER BY created_at DESC
            ''') as cursor:
                rows = await cursor.fetchall()
                return [{
                    'user_id': row[0],
                    'username': row[1],
                    'full_name': row[2],
                    'role': row[3],
                    'created_at': row[4]
                } for row in rows]
    
    # Методы для работы с отзывами
    async def add_review(self, user_id: int, room_id: int, review_text: str) -> int:
        """Добавить отзыв"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                INSERT INTO reviews (user_id, room_id, review_text)
                VALUES (?, ?, ?)
            ''', (user_id, room_id, review_text))
            await db.commit()
            return cursor.lastrowid
    
    async def get_all_reviews(self) -> List[Dict]:
        """Получить все отзывы"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT r.review_id, r.user_id, r.room_id, r.review_text, r.admin_reply,
                       r.created_at, r.updated_at,
                       u.username, u.full_name,
                       rm.room_name
                FROM reviews r
                JOIN users u ON r.user_id = u.user_id
                LEFT JOIN rooms rm ON r.room_id = rm.room_id
                ORDER BY r.created_at DESC
            ''') as cursor:
                rows = await cursor.fetchall()
                return [{
                    'review_id': row[0],
                    'user_id': row[1],
                    'room_id': row[2],
                    'review_text': row[3],
                    'admin_reply': row[4],
                    'created_at': row[5],
                    'updated_at': row[6],
                    'username': row[7],
                    'full_name': row[8],
                    'room_name': row[9]
                } for row in rows]
    
    async def add_admin_reply(self, review_id: int, reply_text: str):
        """Добавить ответ администратора на отзыв"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE reviews 
                SET admin_reply = ?, updated_at = CURRENT_TIMESTAMP
                WHERE review_id = ?
            ''', (reply_text, review_id))
            await db.commit()
    
    async def delete_review(self, review_id: int):
        """Удалить отзыв"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('DELETE FROM reviews WHERE review_id = ?', (review_id,))
            await db.commit()
    
    async def get_review(self, review_id: int) -> Optional[Dict]:
        """Получить отзыв по ID"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT review_id, user_id, room_id, review_text, admin_reply, created_at, updated_at
                FROM reviews WHERE review_id = ?
            ''', (review_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        'review_id': row[0],
                        'user_id': row[1],
                        'room_id': row[2],
                        'review_text': row[3],
                        'admin_reply': row[4],
                        'created_at': row[5],
                        'updated_at': row[6]
                    }
                return None
    
    # Методы для работы с историей заказов
    async def add_to_order_history(self, room_id: int, closed_by: int):
        """Добавить комнату в историю заказов"""
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем информацию о комнате
            async with db.execute('''
                SELECT room_name, customer_id, created_by, created_at
                FROM rooms WHERE room_id = ?
            ''', (room_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    await db.execute('''
                        INSERT INTO order_history (room_id, room_name, customer_id, created_by, closed_by, room_created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (room_id, row[0], row[1], row[2], closed_by, row[3]))
                    # Обновляем статус комнаты
                    try:
                        await db.execute('UPDATE rooms SET status = "closed" WHERE room_id = ?', (room_id,))
                    except:
                        pass  # Поле status может не существовать
                    await db.commit()
    
    async def get_order_history(self) -> List[Dict]:
        """Получить историю заказов"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT h.history_id, h.room_id, h.room_name, h.customer_id, h.created_by, h.closed_by,
                       h.closed_at, h.room_created_at,
                       u1.username as customer_username, u1.full_name as customer_name,
                       u2.username as creator_username, u2.full_name as creator_name,
                       u3.username as closer_username, u3.full_name as closer_name
                FROM order_history h
                LEFT JOIN users u1 ON h.customer_id = u1.user_id
                LEFT JOIN users u2 ON h.created_by = u2.user_id
                LEFT JOIN users u3 ON h.closed_by = u3.user_id
                ORDER BY h.closed_at DESC
            ''') as cursor:
                rows = await cursor.fetchall()
                return [{
                    'history_id': row[0],
                    'room_id': row[1],
                    'room_name': row[2],
                    'customer_id': row[3],
                    'created_by': row[4],
                    'closed_by': row[5],
                    'closed_at': row[6],
                    'room_created_at': row[7],
                    'customer_username': row[8],
                    'customer_name': row[9],
                    'creator_username': row[10],
                    'creator_name': row[11],
                    'closer_username': row[12],
                    'closer_name': row[13]
                } for row in rows]
    
    async def delete_from_order_history(self, history_id: int):
        """Окончательно удалить заказ из истории"""
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем room_id перед удалением
            async with db.execute('SELECT room_id FROM order_history WHERE history_id = ?', (history_id,)) as cursor:
                row = await cursor.fetchone()
                room_id = row[0] if row else None
            
            # Удаляем из истории
            await db.execute('DELETE FROM order_history WHERE history_id = ?', (history_id,))
            
            # Если комната еще существует, окончательно удаляем её
            if room_id:
                await self.delete_room(room_id)
            
            await db.commit()
    
    async def get_room_status(self, room_id: int) -> str:
        """Получить статус комнаты"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                async with db.execute('SELECT status FROM rooms WHERE room_id = ?', (room_id,)) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else 'active'
            except:
                return 'active'  # Если поле status не существует
    
    async def get_customer_closed_orders(self, customer_id: int) -> List[Dict]:
        """Получить закрытые заказы клиента (где он был клиентом)"""
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем закрытые заказы, где пользователь был клиентом
            async with db.execute('''
                SELECT DISTINCT h.history_id, h.room_id, h.room_name, h.closed_at,
                       CASE WHEN r.review_id IS NOT NULL THEN 1 ELSE 0 END as has_review
                FROM order_history h
                LEFT JOIN reviews r ON h.room_id = r.room_id AND r.user_id = ?
                WHERE h.customer_id = ?
                ORDER BY h.closed_at DESC
            ''', (customer_id, customer_id)) as cursor:
                rows = await cursor.fetchall()
                return [{
                    'history_id': row[0],
                    'room_id': row[1],
                    'room_name': row[2],
                    'closed_at': row[3],
                    'has_review': row[4]
                } for row in rows]

