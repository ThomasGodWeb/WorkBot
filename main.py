import asyncio
import logging
import aiosqlite
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from config import BOT_TOKEN, ADMIN_IDS
from database import Database

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Инициализация базы данных
db = Database()

# Словарь для хранения активных комнат пользователей (user_id -> room_id)
user_active_rooms = {}

# Словарь для хранения активных чатов администраторов (admin_id -> chat_id)
admin_active_chats = {}

# Словарь для хранения состояния пользователей (user_id -> 'add_access' или 'remove_access')
user_action_state = {}

# Словарь для хранения данных о добавлении доступа (user_id -> {'room_id': int, 'role': str})
room_access_state = {}


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id in ADMIN_IDS


async def check_is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором (с проверкой в БД)"""
    if user_id in ADMIN_IDS:
        return True
    role = await db.get_user_role(user_id)
    return role == 'admin'


def is_admin_sync(user_id: int) -> bool:
    """Синхронная проверка администратора (только из конфига)"""
    return user_id in ADMIN_IDS


async def set_user_admin(user_id: int):
    """Установить пользователя как администратора"""
    await db.add_user(user_id, role='admin')


def get_admin_keyboard():
    """Создать клавиатуру для администратора"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Создать комнату", callback_data="action_create_room")
    builder.button(text="📂 Мои комнаты", callback_data="action_my_rooms")
    builder.button(text="🌐 Все комнаты", callback_data="action_all_rooms")
    builder.button(text="💬 Чаты", callback_data="action_chats")
    builder.button(text="👥 База заказчиков", callback_data="action_customers")
    builder.button(text="🔔 Уведомления", callback_data="action_notifications")
    builder.button(text="⭐ Отзывы", callback_data="action_reviews")
    builder.button(text="📜 История заказов", callback_data="action_order_history")
    builder.button(text="➕ Добавить доступ", callback_data="action_add_access")
    builder.button(text="➖ Удалить доступ", callback_data="action_remove_access")
    builder.button(text="🗑️ Удалить комнату", callback_data="action_delete_room")
    builder.button(text="👑 Управление ролями", callback_data="action_manage_roles")
    builder.adjust(2, 2, 2, 2, 2)
    return builder.as_markup()


def get_user_keyboard():
    """Создать клавиатуру для обычного пользователя"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📂 Мои комнаты", callback_data="action_my_rooms")
    builder.button(text="⭐ Отзывы", callback_data="action_reviews")
    builder.button(text="✍️ Оставить отзыв", callback_data="action_add_review")
    builder.button(text="🔄 Обновить меню", callback_data="action_refresh")
    builder.adjust(2, 1, 1)
    return builder.as_markup()


def get_back_to_menu_keyboard(is_admin_user: bool):
    """Создать кнопку возврата в меню"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Главное меню", callback_data="action_menu")
    return builder.as_markup()


def get_reply_admin_keyboard():
    """Создать Reply клавиатуру для администратора"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="🏠 Создать комнату")
    builder.button(text="📂 Мои комнаты")
    builder.button(text="🌐 Все комнаты")
    builder.button(text="➕ Добавить доступ")
    builder.button(text="➖ Удалить доступ")
    builder.button(text="🗑️ Удалить комнату")
    builder.button(text="👑 Управление ролями")
    builder.button(text="🔙 Главное меню")
    builder.adjust(2, 2, 2, 2, 1)
    return builder.as_markup(resize_keyboard=True)


def get_reply_user_keyboard():
    """Создать Reply клавиатуру для обычного пользователя"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="📂 Мои комнаты")
    builder.button(text="🔙 Главное меню")
    builder.adjust(2, 1)
    return builder.as_markup(resize_keyboard=True)


def get_reply_room_keyboard():
    """Создать Reply клавиатуру для управления комнатой (администратор)"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="✏️ Изменить название")
    builder.button(text="➕ Добавить участника")
    builder.button(text="👥 Участники")
    builder.button(text="🗑️ Удалить комнату")
    builder.button(text="🚪 Выйти из комнаты")
    builder.button(text="🔙 Главное меню")
    builder.adjust(2, 2, 2)
    return builder.as_markup(resize_keyboard=True)


@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name
    
    # Добавляем пользователя в базу
    is_user_admin = await check_is_admin(user_id)
    role = 'admin' if is_user_admin else 'user'
    await db.add_user(user_id, username, full_name, role)
    
    if is_user_admin:
        text = (
            "🎉 <b>Добро пожаловать, администратор!</b>\n\n"
            "✨ Вы имеете полный доступ к управлению ботом.\n\n"
            "👇 Используйте кнопки ниже для быстрого доступа к функциям:\n\n"
            "💡 Также доступны команды через <code>/</code>"
        )
        await message.answer(
            text, 
            parse_mode="HTML", 
            reply_markup=get_admin_keyboard()
        )
        # Добавляем Reply клавиатуру
        await message.answer(
            "💡 <b>Используйте кнопки внизу экрана для быстрого доступа!</b>",
            parse_mode="HTML",
            reply_markup=get_reply_admin_keyboard()
        )
    else:
        # Проверяем, есть ли у пользователя комнаты
        rooms = await db.get_user_rooms(user_id, False)
        
        if not rooms:
            # У пользователя нет комнат - он может писать в бота
            text = (
                "👋 <b>Добро пожаловать!</b>\n\n"
                "💬 Вы можете написать нам прямо здесь!\n\n"
                "📝 Просто отправьте ваше сообщение, и администраторы свяжутся с вами.\n\n"
                "⏳ После создания комнаты вы сможете общаться с разработчиками."
            )
            await message.answer(
                text, 
                parse_mode="HTML"
            )
        else:
            # У пользователя есть комнаты - показываем меню
            text = (
                "👋 <b>Добро пожаловать!</b>\n\n"
                "🎯 Вы можете общаться в комнатах, к которым у вас есть доступ.\n\n"
                "👇 Используйте кнопки ниже для навигации:\n\n"
                "💬 После входа в комнату все ваши сообщения будут автоматически отправляться участникам."
            )
            await message.answer(
                text, 
                parse_mode="HTML", 
                reply_markup=get_user_keyboard()
            )
            # Добавляем Reply клавиатуру
            await message.answer(
                "💡 <b>Используйте кнопки внизу экрана для быстрого доступа!</b>",
                parse_mode="HTML",
                reply_markup=get_reply_user_keyboard()
            )


@dp.message(Command("create_room"))
async def cmd_create_room(message: Message):
    """Создать новую комнату (только для админов)"""
    if not await check_is_admin(message.from_user.id):
        await message.answer(
            "🚫 <b>Доступ запрещен</b>\n\n"
            "❌ У вас нет прав для выполнения этой команды.\n"
            "👑 Только администраторы могут создавать комнаты.",
            parse_mode="HTML",
            reply_markup=get_back_to_menu_keyboard(False)
        )
        return
    
    user_action_state[message.from_user.id] = 'create_room'
    await message.answer(
        "🏠 <b>Создание новой комнаты</b>\n\n"
        "📝 Отправьте название комнаты:\n\n"
        "💡 <b>Варианты:</b>\n"
        "• Просто название: <code>Проект X</code>\n"
        "• С заказчиком: <code>Проект X | 123456789</code>\n\n"
        "ℹ️ Если не указать заказчика, его можно добавить позже.\n\n"
        "❌ Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard(True)
    )
    # Показываем Reply клавиатуру
    is_user_admin = await check_is_admin(message.from_user.id)
    await message.answer(
        "💡 Используйте кнопки внизу для быстрого доступа!",
        reply_markup=get_reply_admin_keyboard() if is_user_admin else get_reply_user_keyboard()
    )


@dp.message(Command("my_rooms"))
async def cmd_my_rooms(message: Message):
    """Показать комнаты пользователя"""
    user_id = message.from_user.id
    is_user_admin = await check_is_admin(user_id)
    rooms = await db.get_user_rooms(user_id, is_user_admin)
    
    if not rooms:
        await message.answer(
            "📭 <b>Комнаты не найдены</b>\n\n"
            "😔 У вас пока нет доступа ни к одной комнате.\n\n"
            "💡 Обратитесь к администратору для получения доступа.",
            parse_mode="HTML",
            reply_markup=get_back_to_menu_keyboard(is_user_admin)
        )
        await message.answer(
            "💡 Используйте кнопки внизу!",
            reply_markup=get_reply_admin_keyboard() if is_user_admin else get_reply_user_keyboard()
        )
        return
    
    builder = InlineKeyboardBuilder()
    for room in rooms:
        room_name = room['room_name']
        room_id = room['room_id']
        if room['access_type'] == 'customer':
            access_type = "👤 Заказчик"
        else:
            access_type = "👨‍💻 Разработчик"
        builder.button(
            text=f"🏠 {room_name} ({access_type})",
            callback_data=f"room_{room_id}"
        )
    
    builder.button(text="🔙 Главное меню", callback_data="action_menu")
    builder.adjust(1)
    
    await message.answer(
        f"📂 <b>Ваши комнаты</b>\n\n"
        f"🎯 Найдено комнат: <b>{len(rooms)}</b>\n\n"
        f"👇 Выберите комнату для входа:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await message.answer(
        "💡 Используйте кнопки внизу для быстрого доступа!",
        reply_markup=get_reply_admin_keyboard() if is_user_admin else get_reply_user_keyboard()
    )


@dp.message(Command("add_access"))
async def cmd_add_access(message: Message):
    """Добавить доступ к комнате (только для админов)"""
    if not await check_is_admin(message.from_user.id):
        await message.answer(
            "🚫 <b>Доступ запрещен</b>\n\n"
            "❌ У вас нет прав для выполнения этой команды.",
            parse_mode="HTML",
            reply_markup=get_back_to_menu_keyboard(False)
        )
        return
    
    user_action_state[message.from_user.id] = 'add_access'
    await message.answer(
        "➕ <b>Добавление доступа к комнате</b>\n\n"
        "📝 Отправьте сообщение в следующем формате:\n\n"
        "<code>ID комнаты | ID пользователя</code>\n\n"
        "💡 <b>Пример:</b>\n"
        "<code>1 | 123456789</code>\n\n"
        "⚠️ Используйте символ <b>|</b> (вертикальная черта) для разделения.\n\n"
        "❌ Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard(True)
    )


@dp.message(Command("remove_access"))
async def cmd_remove_access(message: Message):
    """Удалить доступ к комнате (только для админов)"""
    if not await check_is_admin(message.from_user.id):
        await message.answer(
            "🚫 <b>Доступ запрещен</b>\n\n"
            "❌ У вас нет прав для выполнения этой команды.",
            parse_mode="HTML",
            reply_markup=get_back_to_menu_keyboard(False)
        )
        return
    
    user_action_state[message.from_user.id] = 'remove_access'
    await message.answer(
        "➖ <b>Удаление доступа к комнате</b>\n\n"
        "📝 Отправьте сообщение в следующем формате:\n\n"
        "<code>ID комнаты | ID пользователя</code>\n\n"
        "💡 <b>Пример:</b>\n"
        "<code>1 | 123456789</code>\n\n"
        "⚠️ Используйте символ <b>|</b> (вертикальная черта) для разделения.\n\n"
        "❌ Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard(True)
    )


@dp.message(Command("all_rooms"))
async def cmd_all_rooms(message: Message):
    """Показать все комнаты (только для админов)"""
    if not await check_is_admin(message.from_user.id):
        await message.answer(
            "🚫 <b>Доступ запрещен</b>\n\n"
            "❌ У вас нет прав для выполнения этой команды.",
            parse_mode="HTML",
            reply_markup=get_back_to_menu_keyboard(False)
        )
        return
    
    rooms = await db.get_all_rooms()
    
    if not rooms:
        await message.answer(
            "📭 <b>Комнаты не найдены</b>\n\n"
            "😔 В системе пока нет созданных комнат.\n\n"
            "💡 Используйте кнопку создания комнаты для создания первой.",
            parse_mode="HTML",
            reply_markup=get_back_to_menu_keyboard(True)
        )
        return
    
    text = f"🌐 <b>Все комнаты в системе</b>\n\n"
    text += f"📊 Всего комнат: <b>{len(rooms)}</b>\n\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for room in rooms:
        text += f"🏠 <b>{room['room_name']}</b>\n"
        text += f"🆔 ID: <code>{room['room_id']}</code>\n"
        text += f"👤 Заказчик: <code>{room['customer_id']}</code>\n"
        text += f"👑 Создатель: <code>{room['created_by']}</code>\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    await message.answer(text, parse_mode="HTML", reply_markup=get_back_to_menu_keyboard(True))


@dp.message(Command("delete_room"))
async def cmd_delete_room(message: Message):
    """Удалить комнату (только для админов)"""
    if not await check_is_admin(message.from_user.id):
        await message.answer(
            "🚫 <b>Доступ запрещен</b>\n\n"
            "❌ У вас нет прав для выполнения этой команды.",
            parse_mode="HTML",
            reply_markup=get_back_to_menu_keyboard(False)
        )
        return
    
    user_action_state[message.from_user.id] = 'delete_room'
    await message.answer(
        "🗑️ <b>Удаление комнаты</b>\n\n"
        "⚠️ <b>ВНИМАНИЕ:</b> Это действие необратимо!\n"
        "Будут удалены все сообщения и доступы к комнате.\n\n"
        "📝 Отправьте <b>ID комнаты</b> для удаления:\n\n"
        "💡 <b>Пример:</b>\n"
        "<code>1</code>\n\n"
        "❌ Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard(True)
    )


@dp.message(Command("add_admin"))
async def cmd_add_admin(message: Message):
    """Добавить администратора (только для админов)"""
    if not await check_is_admin(message.from_user.id):
        await message.answer(
            "🚫 <b>Доступ запрещен</b>\n\n"
            "❌ У вас нет прав для выполнения этой команды.",
            parse_mode="HTML",
            reply_markup=get_back_to_menu_keyboard(False)
        )
        return
    
    user_action_state[message.from_user.id] = 'add_admin'
    await message.answer(
        "👑 <b>Добавление администратора</b>\n\n"
        "📝 Отправьте <b>Telegram ID</b> пользователя, которого хотите сделать администратором:\n\n"
        "💡 <b>Пример:</b>\n"
        "<code>123456789</code>\n\n"
        "ℹ️ Чтобы узнать ID пользователя, попросите его написать боту @userinfobot\n\n"
        "❌ Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard(True)
    )


@dp.callback_query(lambda c: c.data == "action_menu")
async def process_menu(callback: CallbackQuery):
    """Обработка возврата в главное меню"""
    user_id = callback.from_user.id
    is_user_admin = await check_is_admin(user_id)
    
    if is_user_admin:
        text = (
            "🎉 <b>Главное меню</b>\n\n"
            "✨ Выберите действие из меню ниже:"
        )
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_keyboard())
    else:
        text = (
            "👋 <b>Главное меню</b>\n\n"
            "🎯 Выберите действие из меню ниже:"
        )
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_user_keyboard())
    await callback.answer()


@dp.callback_query(lambda c: c.data == "action_create_room")
async def process_create_room_button(callback: CallbackQuery):
    """Обработка кнопки создания комнаты"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    user_action_state[callback.from_user.id] = 'create_room'
    await callback.message.edit_text(
        "🏠 <b>Создание новой комнаты</b>\n\n"
        "📝 Отправьте название комнаты:\n\n"
        "💡 <b>Варианты:</b>\n"
        "• Просто название: <code>Проект X</code>\n"
        "• С заказчиком: <code>Проект X | 123456789</code>\n\n"
        "ℹ️ Если не указать заказчика, его можно добавить позже.\n\n"
        "❌ Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard(True)
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "action_my_rooms")
async def process_my_rooms_button(callback: CallbackQuery):
    """Обработка кнопки моих комнат"""
    user_id = callback.from_user.id
    is_user_admin = await check_is_admin(user_id)
    rooms = await db.get_user_rooms(user_id, is_user_admin)
    
    if not rooms:
        await callback.message.edit_text(
            "📭 <b>Комнаты не найдены</b>\n\n"
            "😔 У вас пока нет доступа ни к одной комнате.\n\n"
            "💡 Обратитесь к администратору для получения доступа.",
            parse_mode="HTML",
            reply_markup=get_back_to_menu_keyboard(await check_is_admin(user_id))
        )
        await callback.answer()
        return
    
    builder = InlineKeyboardBuilder()
    for room in rooms:
        room_name = room['room_name']
        room_id = room['room_id']
        if room['access_type'] == 'customer':
            access_type = "👤 Заказчик"
        else:
            access_type = "👨‍💻 Разработчик"
        builder.button(
            text=f"🏠 {room_name} ({access_type})",
            callback_data=f"room_{room_id}"
        )
    
    builder.button(text="🔙 Главное меню", callback_data="action_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(
        f"📂 <b>Ваши комнаты</b>\n\n"
        f"🎯 Найдено комнат: <b>{len(rooms)}</b>\n\n"
        f"👇 Выберите комнату для входа:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "action_all_rooms")
async def process_all_rooms_button(callback: CallbackQuery):
    """Обработка кнопки всех комнат"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    rooms = await db.get_all_rooms()
    
    if not rooms:
        await callback.message.edit_text(
            "📭 <b>Комнаты не найдены</b>\n\n"
            "😔 В системе пока нет созданных комнат.\n\n"
            "💡 Используйте кнопку создания комнаты для создания первой.",
            parse_mode="HTML",
            reply_markup=get_back_to_menu_keyboard(True)
        )
        await callback.answer()
        return
    
    text = f"🌐 <b>Все комнаты в системе</b>\n\n"
    text += f"📊 Всего комнат: <b>{len(rooms)}</b>\n\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for room in rooms:
        text += f"🏠 <b>{room['room_name']}</b>\n"
        text += f"🆔 ID: <code>{room['room_id']}</code>\n"
        text += f"👤 Заказчик: <code>{room['customer_id']}</code>\n"
        text += f"👑 Создатель: <code>{room['created_by']}</code>\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_to_menu_keyboard(True))
    await callback.answer()


@dp.callback_query(lambda c: c.data == "action_add_access")
async def process_add_access_button(callback: CallbackQuery):
    """Обработка кнопки добавления доступа"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    user_action_state[callback.from_user.id] = 'add_access'
    await callback.message.edit_text(
        "➕ <b>Добавление доступа к комнате</b>\n\n"
        "📝 Отправьте сообщение в следующем формате:\n\n"
        "<code>ID комнаты | ID пользователя</code>\n\n"
        "💡 <b>Пример:</b>\n"
        "<code>1 | 123456789</code>\n\n"
        "⚠️ Используйте символ <b>|</b> (вертикальная черта) для разделения.\n\n"
        "❌ Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard(True)
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "action_remove_access")
async def process_remove_access_button(callback: CallbackQuery):
    """Обработка кнопки удаления доступа"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    user_action_state[callback.from_user.id] = 'remove_access'
    await callback.message.edit_text(
        "➖ <b>Удаление доступа к комнате</b>\n\n"
        "📝 Отправьте сообщение в следующем формате:\n\n"
        "<code>ID комнаты | ID пользователя</code>\n\n"
        "💡 <b>Пример:</b>\n"
        "<code>1 | 123456789</code>\n\n"
        "⚠️ Используйте символ <b>|</b> (вертикальная черта) для разделения.\n\n"
        "❌ Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard(True)
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "action_delete_room")
async def process_delete_room_button(callback: CallbackQuery):
    """Обработка кнопки удаления комнаты"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    user_action_state[callback.from_user.id] = 'delete_room'
    await callback.message.edit_text(
        "🗑️ <b>Удаление комнаты</b>\n\n"
        "⚠️ <b>ВНИМАНИЕ:</b> Это действие необратимо!\n"
        "Будут удалены все сообщения и доступы к комнате.\n\n"
        "📝 Отправьте <b>ID комнаты</b> для удаления:\n\n"
        "💡 <b>Пример:</b>\n"
        "<code>1</code>\n\n"
        "❌ Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard(True)
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "action_manage_roles")
async def process_manage_roles_button(callback: CallbackQuery):
    """Обработка кнопки управления ролями"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    builder = InlineKeyboardBuilder()
    builder.button(text="👑 Администраторы", callback_data="role_list_admin")
    builder.button(text="👥 Клиенты", callback_data="role_list_customer")
    builder.button(text="👨‍💻 Разработчики", callback_data="role_list_developer")
    builder.button(text="👤 Все пользователи", callback_data="role_list_all")
    builder.button(text="➕ Добавить роль", callback_data="role_add_select")
    builder.button(text="🔙 Главное меню", callback_data="action_menu")
    builder.adjust(1, 1, 1, 1, 1, 1)
    
    # Получаем статистику по ролям
    admins = await db.get_users_by_role('admin')
    customers = await db.get_users_by_role('customer')
    developers = await db.get_users_by_role('developer')
    all_users = await db.get_all_users()
    
    text = "👑 <b>Управление ролями</b>\n\n"
    text += "📊 <b>Статистика:</b>\n"
    text += f"👑 Администраторы: <b>{len(admins)}</b>\n"
    text += f"👥 Клиенты: <b>{len(customers)}</b>\n"
    text += f"👨‍💻 Разработчики: <b>{len(developers)}</b>\n"
    text += f"👤 Всего пользователей: <b>{len(all_users)}</b>\n\n"
    text += "👇 Выберите действие:"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("role_list_"))
async def process_role_list(callback: CallbackQuery):
    """Показать список пользователей с определенной ролью"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    role_type = callback.data.split("_")[2]
    
    if role_type == "all":
        users = await db.get_all_users()
        role_name = "Все пользователи"
        role_emoji = "👤"
    elif role_type == "admin":
        users = await db.get_users_by_role('admin')
        role_name = "Администраторы"
        role_emoji = "👑"
    elif role_type == "customer":
        users = await db.get_users_by_role('customer')
        role_name = "Клиенты"
        role_emoji = "👥"
    elif role_type == "developer":
        users = await db.get_users_by_role('developer')
        role_name = "Разработчики"
        role_emoji = "👨‍💻"
    else:
        await callback.answer("❌ Неизвестная роль", show_alert=True)
        return
    
    if not users:
        await callback.message.edit_text(
            f"{role_emoji} <b>{role_name}</b>\n\n"
            f"📭 Пользователей с этой ролью пока нет.\n\n"
            f"💡 Используйте кнопку '➕ Добавить роль' чтобы назначить роль пользователю.",
            parse_mode="HTML",
            reply_markup=get_back_to_menu_keyboard(True)
        )
        await callback.answer()
        return
    
    builder = InlineKeyboardBuilder()
    for user in users:
        username = f"@{user['username']}" if user['username'] else "Без username"
        full_name = user['full_name'] or "Без имени"
        button_text = f"{username} - {full_name}"
        builder.button(text=button_text, callback_data=f"user_role_{user['user_id']}")
    
    builder.button(text="🔙 К управлению ролями", callback_data="action_manage_roles")
    builder.button(text="🔙 Главное меню", callback_data="action_menu")
    builder.adjust(1, 2)
    
    text = f"{role_emoji} <b>{role_name}</b>\n\n"
    text += f"📊 Всего: <b>{len(users)}</b>\n\n"
    text += "👇 Выберите пользователя для управления:"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("user_role_"))
async def process_user_role(callback: CallbackQuery):
    """Показать информацию о пользователе и управление его ролью"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[2])
    
    # Получаем информацию о пользователе
    async with aiosqlite.connect(db.db_path) as db_conn:
        async with db_conn.execute('''
            SELECT user_id, username, full_name, role, created_at
            FROM users WHERE user_id = ?
        ''', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return
            
            user_info = {
                'user_id': row[0],
                'username': row[1],
                'full_name': row[2],
                'role': row[3],
                'created_at': row[4]
            }
    
    role_emoji = {
        'admin': '👑',
        'customer': '👥',
        'developer': '👨‍💻',
        'user': '👤'
    }.get(user_info['role'], '👤')
    
    role_name = {
        'admin': 'Администратор',
        'customer': 'Клиент',
        'developer': 'Разработчик',
        'user': 'Пользователь'
    }.get(user_info['role'], 'Пользователь')
    
    text = f"👤 <b>Информация о пользователе</b>\n\n"
    text += f"👤 <b>Имя:</b> {user_info['full_name'] or 'Без имени'}\n"
    if user_info['username']:
        text += f"📱 <b>Username:</b> @{user_info['username']}\n"
    text += f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
    text += f"{role_emoji} <b>Роль:</b> {role_name}\n"
    text += f"📅 <b>Добавлен:</b> {user_info['created_at']}\n\n"
    text += "💡 Выберите новую роль для пользователя:"
    
    builder = InlineKeyboardBuilder()
    # Кнопки для смены роли
    if user_info['role'] != 'admin':
        builder.button(text="👑 Сделать администратором", callback_data=f"role_set_{user_id}_admin")
    if user_info['role'] != 'customer':
        builder.button(text="👥 Сделать клиентом", callback_data=f"role_set_{user_id}_customer")
    if user_info['role'] != 'developer':
        builder.button(text="👨‍💻 Сделать разработчиком", callback_data=f"role_set_{user_id}_developer")
    if user_info['role'] != 'user':
        builder.button(text="👤 Сделать пользователем", callback_data=f"role_set_{user_id}_user")
    
    builder.button(text="🗑️ Удалить роль (сбросить)", callback_data=f"role_remove_{user_id}")
    builder.button(text="🔙 К списку ролей", callback_data=f"role_list_{user_info['role']}")
    builder.button(text="🔙 К управлению ролями", callback_data="action_manage_roles")
    builder.adjust(1, 1, 1, 1, 1, 2)
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("role_set_"))
async def process_role_set(callback: CallbackQuery):
    """Установить роль пользователю"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    parts = callback.data.split("_")
    user_id = int(parts[2])
    new_role = parts[3]
    
    # Обновляем роль
    await db.update_user_role(user_id, new_role)
    
    # Если роль изменена на "customer", автоматически добавляем в базу заказчиков
    if new_role == 'customer':
        await db.add_or_update_customer(user_id)
    # Если роль изменена на админа или разработчика, удаляем из базы заказчиков
    elif new_role in ['admin', 'developer']:
        await db.remove_customer(user_id)
    
    role_names = {
        'admin': 'Администратор',
        'customer': 'Клиент',
        'developer': 'Разработчик',
        'user': 'Пользователь'
    }
    
    role_emojis = {
        'admin': '👑',
        'customer': '👥',
        'developer': '👨‍💻',
        'user': '👤'
    }
    
    await callback.answer(
        f"{role_emojis.get(new_role, '👤')} Роль изменена на '{role_names.get(new_role, 'Пользователь')}'",
        show_alert=True
    )
    
    # Обновляем информацию о пользователе
    callback.data = f"user_role_{user_id}"
    await process_user_role(callback)


@dp.callback_query(lambda c: c.data.startswith("role_remove_"))
async def process_role_remove(callback: CallbackQuery):
    """Удалить роль (сбросить на user)"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[2])
    
    # Сбрасываем роль на 'user'
    await db.update_user_role(user_id, 'user')
    
    await callback.answer("👤 Роль сброшена на 'Пользователь'", show_alert=True)
    
    # Обновляем информацию о пользователе
    callback.data = f"user_role_{user_id}"
    await process_user_role(callback)


@dp.callback_query(lambda c: c.data == "role_add_select")
async def process_role_add_select(callback: CallbackQuery):
    """Выбор роли для добавления"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    user_action_state[callback.from_user.id] = 'add_role'
    
    builder = InlineKeyboardBuilder()
    builder.button(text="👑 Администратор", callback_data="role_add_admin")
    builder.button(text="👥 Клиент", callback_data="role_add_customer")
    builder.button(text="👨‍💻 Разработчик", callback_data="role_add_developer")
    builder.button(text="👤 Пользователь", callback_data="role_add_user")
    builder.button(text="🔙 К управлению ролями", callback_data="action_manage_roles")
    builder.adjust(1, 1, 1, 1, 1)
    
    await callback.message.edit_text(
        "➕ <b>Добавление роли</b>\n\n"
        "👇 Выберите роль, которую хотите назначить:\n\n"
        "💡 После выбора роли отправьте <b>Telegram ID</b> пользователя.",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("role_add_"))
async def process_role_add(callback: CallbackQuery):
    """Начать процесс добавления роли"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    role = callback.data.split("_")[2]
    
    role_names = {
        'admin': 'Администратор',
        'customer': 'Клиент',
        'developer': 'Разработчик',
        'user': 'Пользователь'
    }
    
    role_emojis = {
        'admin': '👑',
        'customer': '👥',
        'developer': '👨‍💻',
        'user': '👤'
    }
    
    user_action_state[callback.from_user.id] = f'add_role_{role}'
    
    await callback.message.edit_text(
        f"➕ <b>Добавление роли</b>\n\n"
        f"{role_emojis.get(role, '👤')} <b>Роль:</b> {role_names.get(role, 'Пользователь')}\n\n"
        f"📝 Отправьте <b>Telegram ID</b> пользователя:\n\n"
        f"💡 <b>Пример:</b>\n"
        f"<code>123456789</code>\n\n"
        f"ℹ️ Чтобы узнать ID пользователя, попросите его написать боту @userinfobot\n\n"
        f"❌ Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard(True)
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "action_exit_room")
async def process_exit_room_button(callback: CallbackQuery):
    """Обработка кнопки выхода из комнаты"""
    user_id = callback.from_user.id
    is_user_admin = await check_is_admin(user_id)
    
    if user_id in user_active_rooms:
        del user_active_rooms[user_id]
        text = (
            "🚪 <b>Выход из комнаты</b>\n\n"
            "✅ Вы успешно вышли из комнаты.\n\n"
            "💡 Используйте кнопку 'Мои комнаты' чтобы войти в другую комнату."
        )
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_admin_keyboard() if is_user_admin else get_user_keyboard()
        )
        await callback.answer("✅ Вы вышли из комнаты")
    else:
        await callback.answer("ℹ️ Вы не находитесь ни в одной комнате.", show_alert=True)


@dp.callback_query(lambda c: c.data == "action_chats")
async def process_chats_button(callback: CallbackQuery):
    """Обработка кнопки просмотра чатов"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    chats = await db.get_all_chats()
    
    if not chats:
        await callback.message.edit_text(
            "💬 <b>Чаты</b>\n\n"
            "📭 Пока нет активных чатов.\n\n"
            "💡 Новые сообщения от пользователей будут появляться здесь.",
            parse_mode="HTML",
            reply_markup=get_back_to_menu_keyboard(True)
        )
        await callback.answer()
        return
    
    builder = InlineKeyboardBuilder()
    for chat in chats:
        unread_badge = f" ({chat['unread_count']})" if chat['unread_count'] > 0 else ""
        username = f"@{chat['username']}" if chat['username'] else "Без username"
        button_text = f"{username}{unread_badge}"
        builder.button(text=button_text, callback_data=f"chat_{chat['chat_id']}")
    
    builder.button(text="🔙 Главное меню", callback_data="action_menu")
    builder.adjust(1)
    
    text = "💬 <b>Чаты</b>\n\n"
    text += f"📊 Всего чатов: <b>{len(chats)}</b>\n\n"
    text += "👇 Выберите чат для просмотра:"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("chat_"))
async def process_chat_view(callback: CallbackQuery):
    """Обработка просмотра конкретного чата"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    chat_id = int(callback.data.split("_")[1])
    chat = await db.get_chat_by_chat_id(chat_id)
    
    if not chat:
        await callback.answer("❌ Чат не найден", show_alert=True)
        return
    
    # Получаем информацию о пользователе
    await db.add_user(chat['user_id'], None, None, 'user')
    # Получаем username и full_name из базы
    async with aiosqlite.connect(db.db_path) as db_conn:
        async with db_conn.execute('SELECT username, full_name FROM users WHERE user_id = ?', (chat['user_id'],)) as cursor:
            row = await cursor.fetchone()
            username = row[0] if row else None
            full_name = row[1] if row else "Без имени"
    
    # Отмечаем чат как прочитанный
    await db.mark_chat_as_read(chat_id)
    
    # Получаем последние сообщения
    messages = await db.get_chat_messages(chat_id, limit=10)
    messages.reverse()  # Показываем в хронологическом порядке
    
    # Устанавливаем активный чат для администратора
    admin_active_chats[callback.from_user.id] = chat_id
    
    text = f"💬 <b>Чат с пользователем</b>\n\n"
    text += f"👤 <b>Имя:</b> {full_name}\n"
    if username:
        text += f"📱 <b>Username:</b> @{username}\n"
    text += f"🆔 <b>ID:</b> <code>{chat['user_id']}</code>\n\n"
    
    if messages:
        text += "📜 <b>Последние сообщения:</b>\n\n"
        for msg in messages:
            if msg['is_from_user']:
                text += f"👤 <b>Пользователь:</b> {msg['message_text'][:100]}\n\n"
            else:
                text += f"👨‍💼 <b>Администратор:</b> {msg['message_text'][:100]}\n\n"
    else:
        text += "📭 Пока нет сообщений в этом чате.\n\n"
    
    text += "💡 <b>Теперь вы можете отвечать в этом чате!</b>\n"
    text += "📝 Просто отправьте сообщение, и оно будет доставлено пользователю."
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Создать комнату", callback_data=f"create_room_from_chat_{chat_id}")
    builder.button(text="📝 Добавить пометку", callback_data=f"add_note_{chat['user_id']}")
    builder.button(text="👥 База заказчиков", callback_data="action_customers")
    builder.button(text="🔙 К списку чатов", callback_data="action_chats")
    builder.button(text="🔙 Главное меню", callback_data="action_menu")
    builder.adjust(1, 1, 1, 2)
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("create_room_from_chat_"))
async def process_create_room_from_chat(callback: CallbackQuery):
    """Создание комнаты из чата"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    chat_id = int(callback.data.split("_")[-1])
    chat = await db.get_chat_by_chat_id(chat_id)
    
    if not chat:
        await callback.answer("❌ Чат не найден", show_alert=True)
        return
    
    # Показываем выбор роли для пользователя
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 Заказчик", callback_data=f"create_room_role_{chat['user_id']}_customer")
    builder.button(text="👨‍💻 Разработчик", callback_data=f"create_room_role_{chat['user_id']}_developer")
    builder.button(text="🔙 Назад", callback_data=f"chat_{chat_id}")
    builder.adjust(2, 1)
    
    await callback.message.edit_text(
        "🏠 <b>Создание комнаты из чата</b>\n\n"
        f"👤 Пользователь: <code>{chat['user_id']}</code>\n\n"
        "👆 Выберите роль для пользователя в комнате:",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("create_room_role_"))
async def process_create_room_role_selection(callback: CallbackQuery):
    """Выбор роли при создании комнаты из чата"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    parts = callback.data.split("_")
    target_user_id = int(parts[3])
    role = parts[4]  # customer или developer
    
    user_action_state[callback.from_user.id] = f'create_room_from_chat_{target_user_id}_{role}'
    
    role_name = "Заказчик" if role == 'customer' else "Разработчик"
    
    await callback.message.edit_text(
        "🏠 <b>Создание комнаты из чата</b>\n\n"
        f"👤 Пользователь: <code>{target_user_id}</code>\n"
        f"👤 Роль: <b>{role_name}</b>\n\n"
        "📝 Отправьте <b>название комнаты</b>:\n\n"
        "💡 <b>Пример:</b>\n"
        "<code>Проект: Разработка сайта</code>\n\n"
        "❌ Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard(True)
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "action_customers")
async def process_customers_button(callback: CallbackQuery):
    """Обработка кнопки базы заказчиков"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    customers = await db.get_all_customers()
    
    if not customers:
        await callback.message.edit_text(
            "👥 <b>База заказчиков</b>\n\n"
            "📭 Пока нет заказчиков в базе.\n\n"
            "💡 Заказчики автоматически добавляются при первом обращении в бот.",
            parse_mode="HTML",
            reply_markup=get_back_to_menu_keyboard(True)
        )
        await callback.answer()
        return
    
    builder = InlineKeyboardBuilder()
    for customer in customers:
        username = f"@{customer['username']}" if customer['username'] else "Без username"
        button_text = f"{username} - {customer['full_name'] or 'Без имени'}"
        builder.button(text=button_text, callback_data=f"customer_{customer['user_id']}")
    
    builder.button(text="🔙 Главное меню", callback_data="action_menu")
    builder.adjust(1)
    
    text = "👥 <b>База заказчиков</b>\n\n"
    text += f"📊 Всего заказчиков: <b>{len(customers)}</b>\n\n"
    text += "👇 Выберите заказчика для просмотра:"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("customer_"))
async def process_customer_view(callback: CallbackQuery):
    """Просмотр информации о заказчике"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[1])
    customer = await db.get_customer_info(user_id)
    
    # Получаем информацию о пользователе
    async with aiosqlite.connect(db.db_path) as db_conn:
        async with db_conn.execute('SELECT username, full_name FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            username = row[0] if row else None
            full_name = row[1] if row else "Без имени"
    
    text = f"👤 <b>Информация о заказчике</b>\n\n"
    text += f"👤 <b>Имя:</b> {full_name}\n"
    if username:
        text += f"📱 <b>Username:</b> @{username}\n"
    text += f"🆔 <b>ID:</b> <code>{user_id}</code>\n\n"
    
    if customer:
        if customer['notes']:
            text += f"📝 <b>Пометки:</b>\n{customer['notes']}\n\n"
        else:
            text += "📝 <b>Пометки:</b> Нет пометок\n\n"
        text += f"📅 <b>Добавлен:</b> {customer['created_at']}\n"
        text += f"🔄 <b>Обновлен:</b> {customer['updated_at']}\n"
    else:
        text += "📝 <b>Пометки:</b> Нет пометок\n\n"
        text += "💡 Заказчик еще не добавлен в базу с пометками."
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Редактировать пометки", callback_data=f"edit_notes_{user_id}")
    builder.button(text="🗑️ Удалить пометки", callback_data=f"delete_notes_{user_id}")
    builder.button(text="💬 Открыть чат", callback_data=f"chat_from_customer_{user_id}")
    builder.button(text="🔙 К списку заказчиков", callback_data="action_customers")
    builder.button(text="🔙 Главное меню", callback_data="action_menu")
    builder.adjust(1, 1, 1, 2)
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("edit_notes_"))
async def process_edit_notes(callback: CallbackQuery):
    """Редактирование пометок о заказчике"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[2])
    user_action_state[callback.from_user.id] = f'edit_notes_{user_id}'
    
    customer = await db.get_customer_info(user_id)
    current_notes = customer['notes'] if customer and customer['notes'] else ""
    
    await callback.message.edit_text(
        "📝 <b>Редактирование пометок</b>\n\n"
        f"👤 Заказчик: <code>{user_id}</code>\n\n"
        f"📝 <b>Текущие пометки:</b>\n{current_notes or 'Нет пометок'}\n\n"
        "✏️ Отправьте новые пометки:\n\n"
        "💡 <b>Для удаления пометок</b> используйте кнопку '🗑️ Удалить пометки' или отправьте пустое сообщение.\n\n"
        "❌ Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard(True)
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("delete_notes_"))
async def process_delete_notes(callback: CallbackQuery):
    """Удаление пометок о заказчике"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[2])
    
    # Удаляем пометки (устанавливаем в NULL)
    await db.update_customer_notes(user_id, "")
    
    await callback.answer("🗑️ Пометки удалены", show_alert=True)
    
    # Обновляем информацию о заказчике
    callback.data = f"customer_{user_id}"
    await process_customer_view(callback)


@dp.callback_query(lambda c: c.data.startswith("add_note_"))
async def process_add_note(callback: CallbackQuery):
    """Добавление пометки о заказчике"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[2])
    user_action_state[callback.from_user.id] = f'edit_notes_{user_id}'
    
    customer = await db.get_customer_info(user_id)
    current_notes = customer['notes'] if customer and customer['notes'] else ""
    
    await callback.message.edit_text(
        "📝 <b>Добавление пометки</b>\n\n"
        f"👤 Заказчик: <code>{user_id}</code>\n\n"
        f"📝 <b>Текущие пометки:</b>\n{current_notes or 'Нет пометок'}\n\n"
        "✏️ Отправьте пометку (будет добавлена к существующим):\n\n"
        "❌ Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard(True)
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("chat_from_customer_"))
async def process_chat_from_customer(callback: CallbackQuery):
    """Открытие чата из базы заказчиков"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[3])
    chat = await db.get_chat_by_user_id(user_id)
    
    if not chat:
        # Создаем чат, если его нет
        chat_id = await db.get_or_create_chat(user_id)
    else:
        chat_id = chat['chat_id']
    
    # Вызываем process_chat_view напрямую, изменяя callback.data
    callback.data = f'chat_{chat_id}'
    await process_chat_view(callback)


@dp.callback_query(lambda c: c.data == "action_notifications")
async def process_notifications_button(callback: CallbackQuery):
    """Обработка кнопки управления уведомлениями"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    user_id = callback.from_user.id
    rooms = await db.get_user_notification_rooms(user_id)
    
    if not rooms:
        await callback.message.edit_text(
            "🔔 <b>Управление уведомлениями</b>\n\n"
            "📭 У вас пока нет комнат для управления уведомлениями.\n\n"
            "💡 Создайте комнату или получите доступ к существующей.",
            parse_mode="HTML",
            reply_markup=get_back_to_menu_keyboard(True)
        )
        await callback.answer()
        return
    
    builder = InlineKeyboardBuilder()
    for room in rooms:
        status_emoji = "🔔" if room['enabled'] else "🔕"
        button_text = f"{status_emoji} {room['room_name']}"
        builder.button(text=button_text, callback_data=f"toggle_notification_{room['room_id']}")
    
    builder.button(text="🔙 Главное меню", callback_data="action_menu")
    builder.adjust(1)
    
    enabled_count = sum(1 for r in rooms if r['enabled'])
    text = "🔔 <b>Управление уведомлениями</b>\n\n"
    text += f"📊 Всего комнат: <b>{len(rooms)}</b>\n"
    text += f"🔔 Включено: <b>{enabled_count}</b>\n"
    text += f"🔕 Выключено: <b>{len(rooms) - enabled_count}</b>\n\n"
    text += "👇 Выберите комнату для изменения настроек уведомлений:\n\n"
    text += "💡 <b>Уведомления</b> приходят, когда в комнате появляется новое сообщение,\n"
    text += "а вы не находитесь в этой комнате."
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("toggle_notification_"))
async def process_toggle_notification(callback: CallbackQuery):
    """Переключение уведомлений для комнаты"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    room_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    
    # Получаем текущее состояние
    current_state = await db.get_room_notification(user_id, room_id)
    new_state = not current_state
    
    # Обновляем настройку
    await db.set_room_notification(user_id, room_id, new_state)
    
    # Получаем информацию о комнате
    room = await db.get_room(room_id)
    room_name = room['room_name'] if room else f"Комната {room_id}"
    
    status_text = "включены" if new_state else "выключены"
    status_emoji = "🔔" if new_state else "🔕"
    
    await callback.answer(
        f"{status_emoji} Уведомления {status_text} для комнаты '{room_name}'",
        show_alert=True
    )
    
    # Обновляем список уведомлений
    await process_notifications_button(callback)


# Обработчики для отзывов
@dp.callback_query(lambda c: c.data == "action_add_review")
async def process_add_review_button(callback: CallbackQuery):
    """Обработка кнопки 'Оставить отзыв'"""
    user_id = callback.from_user.id
    
    # Получаем закрытые заказы клиента
    closed_orders = await db.get_customer_closed_orders(user_id)
    
    if not closed_orders:
        await callback.message.edit_text(
            "✍️ <b>Оставить отзыв</b>\n\n"
            "📭 У вас пока нет закрытых заказов.\n\n"
            "💡 Отзывы можно оставлять только для закрытых заказов.",
            parse_mode="HTML",
            reply_markup=get_back_to_menu_keyboard(False)
        )
        await callback.answer()
        return
    
    # Фильтруем заказы, для которых еще нет отзыва
    orders_without_review = [order for order in closed_orders if not order['has_review']]
    
    if not orders_without_review:
        await callback.message.edit_text(
            "✍️ <b>Оставить отзыв</b>\n\n"
            "✅ Вы уже оставили отзывы для всех ваших закрытых заказов.\n\n"
            "💡 Спасибо за вашу обратную связь!",
            parse_mode="HTML",
            reply_markup=get_back_to_menu_keyboard(False)
        )
        await callback.answer()
        return
    
    # Показываем список заказов для отзыва
    text = "✍️ <b>Оставить отзыв</b>\n\n"
    text += "📋 <b>Выберите заказ для отзыва:</b>\n\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    builder = InlineKeyboardBuilder()
    for idx, order in enumerate(orders_without_review[:10], 1):
        text += f"<b>{idx}. {order['room_name']}</b>\n"
        text += f"📅 Закрыт: {order['closed_at']}\n\n"
        
        builder.button(
            text=f"⭐ {order['room_name'][:30]}",
            callback_data=f"add_review_{order['room_id']}"
        )
    
    builder.button(text="🔙 Главное меню", callback_data="action_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@dp.callback_query(lambda c: c.data == "action_reviews")
async def process_reviews_button(callback: CallbackQuery):
    """Обработка кнопки отзывов"""
    user_id = callback.from_user.id
    reviews = await db.get_all_reviews()
    
    # Проверяем, есть ли у пользователя закрытые заказы для отзыва
    closed_orders = await db.get_customer_closed_orders(user_id)
    orders_without_review = [order for order in closed_orders if not order['has_review']] if closed_orders else []
    can_write_review = len(orders_without_review) > 0
    
    if not reviews:
        text = (
            "⭐ <b>Отзывы</b>\n\n"
            "📭 Пока нет отзывов.\n\n"
        )
        if can_write_review:
            text += "💡 Вы можете оставить отзыв о закрытых заказах."
        else:
            text += "💡 Клиенты могут оставлять отзывы из своих комнат после закрытия заказа."
        
        builder = InlineKeyboardBuilder()
        if can_write_review:
            builder.button(text="✍️ Написать отзыв", callback_data="action_add_review")
        builder.button(text="🔙 Главное меню", callback_data="action_menu")
        builder.adjust(1) if can_write_review else builder.adjust(1)
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
        await callback.answer()
        return
    
    text = f"⭐ <b>Отзывы</b>\n\n"
    text += f"📊 Всего отзывов: <b>{len(reviews)}</b>\n\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Показываем первые 10 отзывов
    for idx, review in enumerate(reviews[:10], 1):
        text += f"<b>{idx}. Отзыв от {review['full_name'] or 'Пользователь'}</b>\n"
        if review['room_name']:
            text += f"🏠 Комната: {review['room_name']}\n"
        text += f"📅 {review['created_at']}\n"
        text += f"💬 {review['review_text'][:50]}...\n\n"
        if review['admin_reply']:
            text += f"   👑 <b>Ответ администратора:</b> {review['admin_reply'][:50]}...\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    builder = InlineKeyboardBuilder()
    for review in reviews[:10]:
        username = f"@{review['username']}" if review['username'] else f"ID:{review['user_id']}"
        builder.button(
            text=f"⭐ {username} - {review['created_at'][:10]}",
            callback_data=f"review_{review['review_id']}"
        )
    
    if can_write_review:
        builder.button(text="✍️ Написать отзыв", callback_data="action_add_review")
    builder.button(text="🔙 Главное меню", callback_data="action_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("add_review_") and 
                   not c.data.startswith("action_add_review") and
                   len(c.data.split("_")) == 3)
async def process_add_review_select(callback: CallbackQuery):
    """Обработка выбора заказа для отзыва"""
    room_id = int(callback.data.split("_")[2])
    
    # Проверяем, является ли пользователь клиентом этого заказа
    closed_orders = await db.get_customer_closed_orders(callback.from_user.id)
    order = next((o for o in closed_orders if o['room_id'] == room_id), None)
    
    if not order:
        await callback.answer("🚫 У вас нет доступа к этому заказу.", show_alert=True)
        return
    
    if order['has_review']:
        await callback.answer("⚠️ Вы уже оставили отзыв для этого заказа.", show_alert=True)
        return
    
    # Получаем информацию о комнате
    room = await db.get_room(room_id)
    if not room:
        # Если комнаты нет, используем данные из истории
        history = await db.get_order_history()
        order_history = next((h for h in history if h['room_id'] == room_id), None)
        if not order_history:
            await callback.answer("❌ Заказ не найден.", show_alert=True)
            return
        room_name = order_history['room_name']
    else:
        room_name = room['room_name']
    
    # Устанавливаем состояние для добавления отзыва
    user_action_state[callback.from_user.id] = f'add_review_{room_id}'
    
    await callback.message.edit_text(
        "⭐ <b>Оставить отзыв</b>\n\n"
        f"🏠 Заказ: <b>{room_name}</b>\n\n"
        "💬 Поделитесь вашим мнением о работе:\n\n"
        "❌ Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard(False)
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("review_") and 
                   not c.data.startswith("review_reply_") and 
                   not c.data.startswith("review_delete_") and
                   len(c.data.split("_")) == 2)
async def process_review_view(callback: CallbackQuery):
    """Просмотр отзыва"""
    review_id = int(callback.data.split("_")[1])
    review = await db.get_review(review_id)
    
    if not review:
        await callback.answer("❌ Отзыв не найден.", show_alert=True)
        return
    
    # Получаем информацию о пользователе
    async with aiosqlite.connect(db.db_path) as db_conn:
        async with db_conn.execute('SELECT username, full_name FROM users WHERE user_id = ?', (review['user_id'],)) as cursor:
            row = await cursor.fetchone()
            username = row[0] if row else None
            full_name = row[1] if row else "Без имени"
    
    text = f"⭐ <b>Отзыв</b>\n\n"
    text += f"👤 <b>Автор:</b> {full_name}\n"
    if username:
        text += f"📱 <b>Username:</b> @{username}\n"
    text += f"🆔 <b>ID:</b> <code>{review['user_id']}</code>\n"
    text += f"📅 <b>Дата:</b> {review['created_at']}\n\n"
    text += f"💬 <b>Отзыв:</b>\n{review['review_text']}\n\n"
    
    if review['admin_reply']:
        text += f"━━━━━━━━━━━━━━━━━━━━\n\n"
        text += f"👑 <b>Ответ администратора:</b>\n{review['admin_reply']}\n"
        text += f"📅 {review['updated_at']}\n"
    else:
        text += "💡 <b>Ответа администратора пока нет.</b>"
    
    builder = InlineKeyboardBuilder()
    is_admin = await check_is_admin(callback.from_user.id)
    
    if is_admin:
        if not review['admin_reply']:
            builder.button(text="✏️ Ответить на отзыв", callback_data=f"review_reply_{review_id}")
        builder.button(text="🗑️ Удалить отзыв", callback_data=f"review_delete_{review_id}")
    
    builder.button(text="🔙 К списку отзывов", callback_data="action_reviews")
    builder.button(text="🔙 Главное меню", callback_data="action_menu")
    builder.adjust(1, 1, 2) if is_admin else builder.adjust(1, 1)
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("review_reply_"))
async def process_review_reply(callback: CallbackQuery):
    """Обработка ответа на отзыв"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    review_id = int(callback.data.split("_")[2])
    user_action_state[callback.from_user.id] = f'review_reply_{review_id}'
    
    await callback.message.edit_text(
        "✏️ <b>Ответ на отзыв</b>\n\n"
        "📝 Отправьте ваш ответ на отзыв:\n\n"
        "❌ Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard(True)
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("review_delete_"))
async def process_review_delete(callback: CallbackQuery):
    """Удаление отзыва"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    review_id = int(callback.data.split("_")[2])
    await db.delete_review(review_id)
    
    await callback.answer("🗑️ Отзыв удален", show_alert=True)
    
    # Возвращаемся к списку отзывов
    callback.data = "action_reviews"
    await process_reviews_button(callback)


# Обработчики для истории заказов
@dp.callback_query(lambda c: c.data == "action_order_history")
async def process_order_history_button(callback: CallbackQuery):
    """Обработка кнопки истории заказов"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    history = await db.get_order_history()
    
    if not history:
        text = (
            "📜 <b>История заказов</b>\n\n"
            "📭 Пока нет закрытых заказов.\n\n"
            "💡 Закрытые заказы будут отображаться здесь."
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Главное меню", callback_data="action_menu")
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
        await callback.answer()
        return
    
    text = f"📜 <b>История заказов</b>\n\n"
    text += f"📊 Всего закрытых заказов: <b>{len(history)}</b>\n\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Показываем первые 10 заказов
    for idx, order in enumerate(history[:10], 1):
        text += f"<b>{idx}. {order['room_name']}</b>\n"
        if order['customer_name']:
            text += f"👤 Заказчик: {order['customer_name']}\n"
        text += f"📅 Закрыт: {order['closed_at']}\n"
        if order['closer_name']:
            text += f"👑 Закрыл: {order['closer_name']}\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    builder = InlineKeyboardBuilder()
    for order in history[:10]:
        builder.button(
            text=f"📜 {order['room_name'][:30]}",
            callback_data=f"order_history_{order['history_id']}"
        )
    
    builder.button(text="🔙 Главное меню", callback_data="action_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("order_history_"))
async def process_order_history_view(callback: CallbackQuery):
    """Просмотр заказа из истории"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    history_id = int(callback.data.split("_")[2])
    history_list = await db.get_order_history()
    order = next((h for h in history_list if h['history_id'] == history_id), None)
    
    if not order:
        await callback.answer("❌ Заказ не найден.", show_alert=True)
        return
    
    text = f"📜 <b>Информация о заказе</b>\n\n"
    text += f"🏠 <b>Название:</b> {order['room_name']}\n"
    text += f"🆔 <b>ID комнаты:</b> <code>{order['room_id']}</code>\n\n"
    
    if order['customer_name']:
        text += f"👤 <b>Заказчик:</b> {order['customer_name']}\n"
        if order['customer_username']:
            text += f"📱 <b>Username:</b> @{order['customer_username']}\n"
        text += f"🆔 <b>ID:</b> <code>{order['customer_id']}</code>\n\n"
    
    if order['creator_name']:
        text += f"👑 <b>Создатель:</b> {order['creator_name']}\n"
        if order['creator_username']:
            text += f"📱 <b>Username:</b> @{order['creator_username']}\n"
        text += f"🆔 <b>ID:</b> <code>{order['created_by']}</code>\n\n"
    
    if order['closer_name']:
        text += f"✅ <b>Закрыл:</b> {order['closer_name']}\n"
        if order['closer_username']:
            text += f"📱 <b>Username:</b> @{order['closer_username']}\n"
        text += f"🆔 <b>ID:</b> <code>{order['closed_by']}</code>\n\n"
    
    text += f"📅 <b>Создан:</b> {order['room_created_at']}\n"
    text += f"📅 <b>Закрыт:</b> {order['closed_at']}\n"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑️ Окончательно удалить", callback_data=f"order_history_delete_{history_id}")
    builder.button(text="🔙 К истории заказов", callback_data="action_order_history")
    builder.button(text="🔙 Главное меню", callback_data="action_menu")
    builder.adjust(1, 2)
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("order_history_delete_"))
async def process_order_history_delete(callback: CallbackQuery):
    """Окончательное удаление заказа из истории"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    history_id = int(callback.data.split("_")[3])
    await db.delete_from_order_history(history_id)
    
    await callback.answer("🗑️ Заказ окончательно удален", show_alert=True)
    
    # Возвращаемся к истории заказов
    callback.data = "action_order_history"
    await process_order_history_button(callback)


# Обработчики для закрытия заказа
@dp.callback_query(lambda c: c.data.startswith("room_close_") and 
                   not c.data.startswith("room_close_confirm_"))
async def process_room_close(callback: CallbackQuery):
    """Обработка закрытия заказа администратором"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    room_id = int(callback.data.split("_")[2])
    room = await db.get_room(room_id)
    
    if not room:
        await callback.answer("❌ Комната не найдена.", show_alert=True)
        return
    
    # Перемещаем в историю
    await db.add_to_order_history(room_id, callback.from_user.id)
    
    # Удаляем из активных комнат
    if callback.from_user.id in user_active_rooms:
        del user_active_rooms[callback.from_user.id]
    
    await callback.answer("✅ Заказ закрыт и перемещен в историю", show_alert=True)
    
    # Удаляем из активных комнат всех пользователей этой комнаты
    users_to_remove = [uid for uid, rid in user_active_rooms.items() if rid == room_id]
    for uid in users_to_remove:
        del user_active_rooms[uid]
    
    # Уведомляем всех участников
    members = await db.get_room_members(room_id)
    customer_id = None
    for member in members:
        try:
            await bot.send_message(
                member['user_id'],
                f"✅ <b>Заказ закрыт</b>\n\n"
                f"🏠 Комната: <b>{room['room_name']}</b>\n\n"
                f"💡 Заказ был закрыт администратором и перемещен в историю.",
                parse_mode="HTML"
            )
            # Находим клиента
            if member['access_type'] == 'customer':
                customer_id = member['user_id']
        except:
            pass
    
    # Предлагаем клиенту оставить отзыв
    if customer_id:
        try:
            builder = InlineKeyboardBuilder()
            builder.button(text="⭐ Оставить отзыв", callback_data=f"add_review_{room_id}")
            builder.button(text="🔙 Главное меню", callback_data="action_menu")
            builder.adjust(1, 1)
            
            await bot.send_message(
                customer_id,
                f"✅ <b>Заказ закрыт</b>\n\n"
                f"🏠 Комната: <b>{room['room_name']}</b>\n\n"
                f"⭐ <b>Оставить отзыв</b>\n\n"
                f"💬 Поделитесь вашим мнением о работе или нажмите кнопку ниже:",
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
        except:
            pass
    
    # Возвращаемся в главное меню
    text = (
        "🎉 <b>Главное меню</b>\n\n"
        "✨ Выберите действие из меню ниже:"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_keyboard())


@dp.callback_query(lambda c: c.data.startswith("room_close_confirm_"))
async def process_room_close_confirm(callback: CallbackQuery):
    """Подтверждение закрытия заказа клиентом"""
    room_id = int(callback.data.split("_")[3])
    room = await db.get_room(room_id)
    
    if not room:
        await callback.answer("❌ Комната не найдена.", show_alert=True)
        return
    
    # Проверяем, является ли пользователь клиентом
    user_access = await db.get_room_access(room_id, callback.from_user.id)
    if not user_access or user_access.get('access_type') != 'customer':
        await callback.answer("🚫 Только клиент может закрыть заказ.", show_alert=True)
        return
    
    # Проверяем, не закрыта ли комната уже
    try:
        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            async with conn.execute('SELECT COUNT(*) FROM order_history WHERE room_id = ?', (room_id,)) as cursor:
                result = await cursor.fetchone()
                if result and result[0] > 0:
                    await callback.answer("⚠️ Этот заказ уже закрыт.", show_alert=True)
                    return
    except:
        pass
    
    # Перемещаем в историю
    await db.add_to_order_history(room_id, callback.from_user.id)
    
    # Удаляем из активных комнат всех пользователей этой комнаты
    users_to_remove = [uid for uid, rid in user_active_rooms.items() if rid == room_id]
    for uid in users_to_remove:
        del user_active_rooms[uid]
    
    # Уведомляем всех участников
    members = await db.get_room_members(room_id)
    customer_name = callback.from_user.full_name or callback.from_user.username or f"ID: {callback.from_user.id}"
    for member in members:
        try:
            await bot.send_message(
                member['user_id'],
                f"✅ <b>Заказ закрыт</b>\n\n"
                f"🏠 Комната: <b>{room['room_name']}</b>\n\n"
                f"👤 Закрыл клиент: <b>{customer_name}</b>\n\n"
                f"💡 Заказ был закрыт клиентом и перемещен в историю.",
                parse_mode="HTML"
            )
        except:
            pass
    
    # Предлагаем оставить отзыв
    user_action_state[callback.from_user.id] = f'add_review_{room_id}'
    
    await callback.message.edit_text(
        "✅ <b>Заказ закрыт!</b>\n\n"
        f"🏠 Комната: <b>{room['room_name']}</b>\n\n"
        "⭐ <b>Оставить отзыв</b>\n\n"
        "💬 Поделитесь вашим мнением о работе:\n\n"
        "❌ Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard(False)
    )
    await callback.answer("✅ Заказ закрыт!")


@dp.callback_query(lambda c: c.data == "action_refresh")
async def process_refresh_button(callback: CallbackQuery):
    """Обработка кнопки обновления меню"""
    user_id = callback.from_user.id
    is_user_admin = await check_is_admin(user_id)
    
    if is_user_admin:
        text = (
            "🎉 <b>Главное меню</b>\n\n"
            "✨ Выберите действие из меню ниже:"
        )
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_keyboard())
    else:
        text = (
            "👋 <b>Главное меню</b>\n\n"
            "🎯 Выберите действие из меню ниже:"
        )
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_user_keyboard())
    await callback.answer("🔄 Меню обновлено")


@dp.callback_query(lambda c: c.data.startswith("room_") and 
                   not c.data.startswith("room_manage_") and
                   not c.data.startswith("room_edit_") and
                   not c.data.startswith("room_add_access_") and
                   not c.data.startswith("room_members_") and
                   not c.data.startswith("room_delete_") and
                   not c.data.startswith("room_change_role_") and
                   not c.data.startswith("room_remove_member_") and
                   not c.data.startswith("room_role_") and
                   len(c.data.split("_")) == 2)
async def process_room_selection(callback: CallbackQuery):
    """Обработка выбора комнаты"""
    room_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    is_user_admin = await check_is_admin(user_id)
    
    # Проверяем доступ (админы видят все комнаты и автоматически получают доступ)
    if not is_user_admin:
        rooms = await db.get_user_rooms(user_id, False)
        if not any(r['room_id'] == room_id for r in rooms):
            await callback.answer(
                "🚫 У вас нет доступа к этой комнате.",
                show_alert=True
            )
            return
    else:
        # Администратор автоматически получает доступ к комнате, если его еще нет
        rooms = await db.get_user_rooms(user_id, True)
        if not any(r['room_id'] == room_id for r in rooms):
            # Добавляем администратора в комнату с ролью developer
            await db.add_room_access(room_id, user_id, 'developer')
    
    # Устанавливаем активную комнату
    user_active_rooms[user_id] = room_id
    
    room = await db.get_room(room_id)
    if room:
        # Получаем участников комнаты
        members = await db.get_room_members(room_id)
        
        if is_user_admin:
            # Детальная информация для администратора
            text = f"🏠 <b>УПРАВЛЕНИЕ КОМНАТОЙ</b>\n\n"
            text += f"━━━━━━━━━━━━━━━━━━━━\n"
            text += f"📝 <b>Название:</b> {room['room_name']}\n"
            text += f"🆔 <b>ID комнаты:</b> <code>{room_id}</code>\n"
            text += f"👤 <b>Заказчик ID:</b> <code>{room['customer_id']}</code>\n"
            text += f"👑 <b>Создатель ID:</b> <code>{room['created_by']}</code>\n"
            text += f"👥 <b>Участников:</b> {len(members)}\n"
            text += f"━━━━━━━━━━━━━━━━━━━━\n\n"
            
            # Показываем участников с возможностью изменения роли
            if members:
                text += "📋 <b>УЧАСТНИКИ:</b>\n\n"
                for idx, member in enumerate(members, 1):
                    role_emoji = "👤" if member['access_type'] == 'customer' else "👨‍💻"
                    role_name = "Заказчик" if member['access_type'] == 'customer' else "Разработчик"
                    username = f"@{member['username']}" if member['username'] else "Без username"
                    full_name = member['full_name'] if member['full_name'] else "Без имени"
                    text += f"{idx}. {role_emoji} <b>{role_name}</b>\n"
                    text += f"   👤 {full_name}\n"
                    text += f"   📱 {username}\n"
                    text += f"   🆔 ID: <code>{member['user_id']}</code>\n\n"
            else:
                text += "😔 Участников пока нет.\n\n"
            
            text += f"💬 <b>Режим общения активен</b> - все ваши сообщения будут отправляться в эту комнату."
            
            builder = InlineKeyboardBuilder()
            
            # Кнопки быстрого управления
            builder.button(text="✏️ Изменить название", callback_data=f"room_edit_{room_id}")
            builder.button(text="➕ Добавить участника", callback_data=f"room_add_access_{room_id}")
            builder.button(text="👥 Управление участниками", callback_data=f"room_members_{room_id}")
            builder.button(text="✅ Закрыть заказ", callback_data=f"room_close_{room_id}")
            builder.button(text="🗑️ Удалить комнату", callback_data=f"room_delete_{room_id}")
            builder.button(text="🔙 Главное меню", callback_data="action_menu")
            builder.button(text="🚪 Выйти из комнаты", callback_data="action_exit_room")
            builder.adjust(2, 2, 1, 2)
        else:
            # Обычный интерфейс для пользователя
            text = f"✅ <b>Вы вошли в комнату!</b>\n\n"
            text += f"🏠 <b>Комната:</b> {room['room_name']}\n"
            text += f"🆔 <b>ID:</b> <code>{room_id}</code>\n\n"
            
            # Не показываем список участников для клиентов, только для администраторов
            text += f"💬 Теперь все ваши сообщения будут автоматически отправляться в эту комнату.\n\n"
            text += f"📤 Отправляйте текстовые сообщения, фото, видео, документы - все будет переслано участникам."
            
            builder = InlineKeyboardBuilder()
            
            # Проверяем, является ли пользователь клиентом в этой комнате
            user_access = await db.get_room_access(room_id, user_id)
            is_customer = user_access and user_access.get('access_type') == 'customer'
            
            if is_customer:
                builder.button(text="✅ Закрыть заказ", callback_data=f"room_close_confirm_{room_id}")
            
            builder.button(text="🔙 Главное меню", callback_data="action_menu")
            builder.button(text="🚪 Выйти из комнаты", callback_data="action_exit_room")
            builder.adjust(1, 2) if is_customer else builder.adjust(2)
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
        await callback.answer("✅ Вы вошли в комнату!")
        
        # Добавляем Reply клавиатуру для управления комнатой (только для админа)
        if is_user_admin:
            try:
                await bot.send_message(
                    user_id,
                    "💡 <b>Используйте кнопки внизу для управления комнатой!</b>",
                    parse_mode="HTML",
                    reply_markup=get_reply_room_keyboard()
                )
            except:
                pass
    else:
        await callback.answer("❌ Комната не найдена.", show_alert=True)


@dp.callback_query(lambda c: c.data.startswith("room_add_access_"))
async def process_room_add_access(callback: CallbackQuery):
    """Обработка добавления доступа к комнате"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    room_id = int(callback.data.split("_")[3])
    room = await db.get_room(room_id)
    
    if not room:
        await callback.answer("❌ Комната не найдена.", show_alert=True)
        return
    
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 Заказчик", callback_data=f"room_role_{room_id}_customer")
    builder.button(text="👨‍💻 Разработчик", callback_data=f"room_role_{room_id}_developer")
    builder.button(text="🔙 Назад", callback_data=f"room_{room_id}")
    builder.adjust(2, 1)
    
    await callback.message.edit_text(
        f"➕ <b>Добавление доступа к комнате</b>\n\n"
        f"🏠 Комната: <b>{room['room_name']}</b>\n\n"
        f"👆 Выберите роль для нового участника:",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("room_role_"))
async def process_room_role_selection(callback: CallbackQuery):
    """Обработка выбора роли для добавления доступа"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    parts = callback.data.split("_")
    room_id = int(parts[2])
    role = parts[3]  # customer или developer
    
    room = await db.get_room(room_id)
    if not room:
        await callback.answer("❌ Комната не найдена.", show_alert=True)
        return
    
    room_access_state[callback.from_user.id] = {'room_id': room_id, 'role': role}
    
    role_name = "Заказчик" if role == 'customer' else "Разработчик"
    
    await callback.message.edit_text(
        f"➕ <b>Добавление доступа</b>\n\n"
        f"🏠 Комната: <b>{room['room_name']}</b>\n"
        f"👤 Роль: <b>{role_name}</b>\n\n"
        f"📝 Отправьте <b>Telegram ID</b> пользователя, которого хотите добавить:\n\n"
        f"💡 <b>Пример:</b>\n"
        f"<code>123456789</code>\n\n"
        f"❌ Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard(True)
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("room_members_"))
async def process_room_members(callback: CallbackQuery):
    """Обработка просмотра участников комнаты"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    room_id = int(callback.data.split("_")[2])
    room = await db.get_room(room_id)
    
    if not room:
        await callback.answer("❌ Комната не найдена.", show_alert=True)
        return
    
    members = await db.get_room_members(room_id)
    
    text = f"👥 <b>УПРАВЛЕНИЕ УЧАСТНИКАМИ</b>\n\n"
    text += f"🏠 Комната: <b>{room['room_name']}</b>\n"
    text += f"🆔 ID: <code>{room_id}</code>\n"
    text += f"📊 Всего участников: <b>{len(members)}</b>\n\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    if members:
        for member in members:
            role_emoji = "👤" if member['access_type'] == 'customer' else "👨‍💻"
            role_name = "Заказчик" if member['access_type'] == 'customer' else "Разработчик"
            username = f"@{member['username']}" if member['username'] else "Без username"
            full_name = member['full_name'] if member['full_name'] else "Без имени"
            text += f"{role_emoji} <b>{role_name}</b>\n"
            text += f"   👤 {full_name}\n"
            text += f"   📱 {username}\n"
            text += f"   🆔 ID: <code>{member['user_id']}</code>\n"
            text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    else:
        text += "😔 Участников пока нет.\n\n"
    
    builder = InlineKeyboardBuilder()
    
    # Кнопки для каждого участника (изменить роль/удалить)
    if members:
        for member in members:
            current_role = member['access_type']
            new_role = 'developer' if current_role == 'customer' else 'customer'
            role_text = "👨‍💻→👤" if current_role == 'developer' else "👤→👨‍💻"
            username_display = f"@{member['username']}" if member['username'] else f"ID:{member['user_id']}"
            builder.button(
                text=f"{role_text} {username_display}",
                callback_data=f"room_change_role_{room_id}_{member['user_id']}_{new_role}"
            )
            builder.button(
                text=f"❌ Удалить {username_display}",
                callback_data=f"room_remove_member_{room_id}_{member['user_id']}"
            )
        builder.adjust(1, 1)
        builder.button(text="➕ Добавить участника", callback_data=f"room_add_access_{room_id}")
        builder.button(text="🔙 К комнате", callback_data=f"room_{room_id}")
        builder.adjust(1)
    else:
        builder.button(text="➕ Добавить участника", callback_data=f"room_add_access_{room_id}")
        builder.button(text="🔙 К комнате", callback_data=f"room_{room_id}")
        builder.adjust(1)
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("room_change_role_"))
async def process_room_change_role(callback: CallbackQuery):
    """Обработка изменения роли участника"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    parts = callback.data.split("_")
    room_id = int(parts[3])
    target_user_id = int(parts[4])
    new_role = parts[5]  # customer или developer
    
    room = await db.get_room(room_id)
    if not room:
        await callback.answer("❌ Комната не найдена.", show_alert=True)
        return
    
    # Обновляем роль
    await db.update_user_role_in_room(room_id, target_user_id, new_role)
    
    # Если роль изменена на customer, добавляем в базу заказчиков и обновляем роль
    if new_role == 'customer':
        await db.update_user_role(target_user_id, 'customer')
        await db.add_or_update_customer(target_user_id)
    
    role_name = "Заказчик" if new_role == 'customer' else "Разработчик"
    
    # Уведомляем пользователя
    try:
        await bot.send_message(
            target_user_id,
            f"🔄 <b>Роль изменена</b>\n\n"
            f"🏠 Комната: <b>{room['room_name']}</b>\n"
            f"👤 Ваша новая роль: <b>{role_name}</b>",
            parse_mode="HTML"
        )
    except:
        pass
    
    # Обновляем список участников
    members = await db.get_room_members(room_id)
    
    text = f"👥 <b>УПРАВЛЕНИЕ УЧАСТНИКАМИ</b>\n\n"
    text += f"🏠 Комната: <b>{room['room_name']}</b>\n"
    text += f"🆔 ID: <code>{room_id}</code>\n"
    text += f"📊 Всего участников: <b>{len(members)}</b>\n\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    if members:
        for member in members:
            role_emoji = "👤" if member['access_type'] == 'customer' else "👨‍💻"
            role_name_member = "Заказчик" if member['access_type'] == 'customer' else "Разработчик"
            username = f"@{member['username']}" if member['username'] else "Без username"
            full_name = member['full_name'] if member['full_name'] else "Без имени"
            text += f"{role_emoji} <b>{role_name_member}</b>\n"
            text += f"   👤 {full_name}\n"
            text += f"   📱 {username}\n"
            text += f"   🆔 ID: <code>{member['user_id']}</code>\n"
            text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    else:
        text += "😔 Участников пока нет.\n\n"
    
    builder = InlineKeyboardBuilder()
    
    # Кнопки для каждого участника (изменить роль/удалить)
    if members:
        for member in members:
            current_role = member['access_type']
            new_role_btn = 'developer' if current_role == 'customer' else 'customer'
            role_text = "👨‍💻→👤" if current_role == 'developer' else "👤→👨‍💻"
            username_display = f"@{member['username']}" if member['username'] else f"ID:{member['user_id']}"
            builder.button(
                text=f"{role_text} {username_display}",
                callback_data=f"room_change_role_{room_id}_{member['user_id']}_{new_role_btn}"
            )
            builder.button(
                text=f"❌ Удалить {username_display}",
                callback_data=f"room_remove_member_{room_id}_{member['user_id']}"
            )
        builder.adjust(1, 1)
        builder.button(text="➕ Добавить участника", callback_data=f"room_add_access_{room_id}")
        builder.button(text="🔙 К комнате", callback_data=f"room_{room_id}")
        builder.adjust(1)
    else:
        builder.button(text="➕ Добавить участника", callback_data=f"room_add_access_{room_id}")
        builder.button(text="🔙 К комнате", callback_data=f"room_{room_id}")
        builder.adjust(1)
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer(f"✅ Роль изменена на {role_name}")


@dp.callback_query(lambda c: c.data.startswith("room_remove_member_"))
async def process_room_remove_member(callback: CallbackQuery):
    """Обработка удаления участника из комнаты"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    parts = callback.data.split("_")
    room_id = int(parts[3])
    target_user_id = int(parts[4])
    
    room = await db.get_room(room_id)
    if not room:
        await callback.answer("❌ Комната не найдена.", show_alert=True)
        return
    
    # Удаляем доступ
    await db.remove_room_access(room_id, target_user_id)
    
    # Удаляем из активных комнат, если пользователь был в этой комнате
    if target_user_id in user_active_rooms and user_active_rooms[target_user_id] == room_id:
        del user_active_rooms[target_user_id]
    
    # Уведомляем пользователя
    try:
        await bot.send_message(
            target_user_id,
            f"🚫 <b>Доступ удален</b>\n\n"
            f"❌ Вам был удален доступ к комнате: <b>{room['room_name']}</b>",
            parse_mode="HTML"
        )
    except:
        pass
    
    # Обновляем список участников
    members = await db.get_room_members(room_id)
    
    text = f"👥 <b>УПРАВЛЕНИЕ УЧАСТНИКАМИ</b>\n\n"
    text += f"🏠 Комната: <b>{room['room_name']}</b>\n"
    text += f"🆔 ID: <code>{room_id}</code>\n"
    text += f"📊 Всего участников: <b>{len(members)}</b>\n\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    if members:
        for member in members:
            role_emoji = "👤" if member['access_type'] == 'customer' else "👨‍💻"
            role_name_member = "Заказчик" if member['access_type'] == 'customer' else "Разработчик"
            username = f"@{member['username']}" if member['username'] else "Без username"
            full_name = member['full_name'] if member['full_name'] else "Без имени"
            text += f"{role_emoji} <b>{role_name_member}</b>\n"
            text += f"   👤 {full_name}\n"
            text += f"   📱 {username}\n"
            text += f"   🆔 ID: <code>{member['user_id']}</code>\n"
            text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    else:
        text += "😔 Участников пока нет.\n\n"
    
    builder = InlineKeyboardBuilder()
    
    # Кнопки для каждого участника
    if members:
        for member in members:
            current_role = member['access_type']
            new_role_btn = 'developer' if current_role == 'customer' else 'customer'
            role_text = "👨‍💻→👤" if current_role == 'developer' else "👤→👨‍💻"
            username_display = f"@{member['username']}" if member['username'] else f"ID:{member['user_id']}"
            builder.button(
                text=f"{role_text} {username_display}",
                callback_data=f"room_change_role_{room_id}_{member['user_id']}_{new_role_btn}"
            )
            builder.button(
                text=f"❌ Удалить {username_display}",
                callback_data=f"room_remove_member_{room_id}_{member['user_id']}"
            )
        builder.adjust(1, 1)
        builder.button(text="➕ Добавить участника", callback_data=f"room_add_access_{room_id}")
        builder.button(text="🔙 К комнате", callback_data=f"room_{room_id}")
        builder.adjust(1)
    else:
        builder.button(text="➕ Добавить участника", callback_data=f"room_add_access_{room_id}")
        builder.button(text="🔙 К комнате", callback_data=f"room_{room_id}")
        builder.adjust(1)
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer("✅ Участник удален")


@dp.callback_query(lambda c: c.data.startswith("room_edit_"))
async def process_room_edit(callback: CallbackQuery):
    """Обработка редактирования комнаты"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    room_id = int(callback.data.split("_")[2])
    room = await db.get_room(room_id)
    
    if not room:
        await callback.answer("❌ Комната не найдена.", show_alert=True)
        return
    
    user_action_state[callback.from_user.id] = f'edit_room_{room_id}'
    
    await callback.message.edit_text(
        f"✏️ <b>Редактирование комнаты</b>\n\n"
        f"🏠 Текущее название: <b>{room['room_name']}</b>\n\n"
        f"📝 Отправьте новое название комнаты:\n\n"
        f"❌ Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard(True)
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("room_delete_") and not c.data.startswith("room_delete_confirm_"))
async def process_room_delete(callback: CallbackQuery):
    """Обработка удаления комнаты"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    room_id = int(callback.data.split("_")[2])
    room = await db.get_room(room_id)
    
    if not room:
        await callback.answer("❌ Комната не найдена.", show_alert=True)
        return
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data=f"room_delete_confirm_{room_id}")
    builder.button(text="❌ Отмена", callback_data=f"room_{room_id}")
    builder.adjust(2)
    
    await callback.message.edit_text(
        f"🗑️ <b>Удаление комнаты</b>\n\n"
        f"⚠️ <b>ВНИМАНИЕ:</b> Это действие необратимо!\n\n"
        f"🏠 Комната: <b>{room['room_name']}</b>\n"
        f"🆔 ID: <code>{room_id}</code>\n\n"
        f"❌ Будут удалены:\n"
        f"   • Все сообщения\n"
        f"   • Все доступы\n"
        f"   • Сама комната\n\n"
        f"⚠️ Вы уверены, что хотите удалить эту комнату?",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("room_delete_confirm_"))
async def process_room_delete_confirm(callback: CallbackQuery):
    """Подтверждение удаления комнаты"""
    if not await check_is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для этого действия.", show_alert=True)
        return
    
    try:
        room_id = int(callback.data.split("_")[3])
        room = await db.get_room(room_id)
        
        if not room:
            await callback.answer("❌ Комната не найдена.", show_alert=True)
            return
        
        room_name = room['room_name']
        
        # Перемещаем комнату в историю заказов вместо удаления
        await db.add_to_order_history(room_id, callback.from_user.id)
        
        # Удаляем из активных комнат всех пользователей
        users_to_remove = [uid for uid, rid in user_active_rooms.items() if rid == room_id]
        for uid in users_to_remove:
            del user_active_rooms[uid]
        
        # Уведомляем всех участников
        members = await db.get_room_members(room_id)
        for member in members:
            try:
                await bot.send_message(
                    member['user_id'],
                    f"🗑️ <b>Комната удалена</b>\n\n"
                    f"🏠 Комната: <b>{room_name}</b>\n\n"
                    f"💡 Комната была удалена администратором и перемещена в историю заказов.",
                    parse_mode="HTML"
                )
            except:
                pass
        
        await callback.message.edit_text(
            f"🗑️ <b>Комната удалена</b>\n\n"
            f"✅ Комната '<b>{room_name}</b>' (ID: {room_id}) перемещена в историю заказов.\n\n"
            f"📜 Вы можете просмотреть её в разделе 'История заказов'.",
            parse_mode="HTML",
            reply_markup=get_back_to_menu_keyboard(True)
        )
        await callback.answer("✅ Комната удалена")
    except Exception as e:
        logger.error(f"Ошибка при удалении комнаты: {e}")
        await callback.answer(f"❌ Ошибка при удалении комнаты: {str(e)}", show_alert=True)


@dp.message(Command("exit_room"))
async def cmd_exit_room(message: Message):
    """Выйти из активной комнаты"""
    user_id = message.from_user.id
    is_user_admin = await check_is_admin(user_id)
    
    if user_id in user_active_rooms:
        del user_active_rooms[user_id]
        await message.answer(
            "🚪 <b>Выход из комнаты</b>\n\n"
            "✅ Вы успешно вышли из комнаты.\n\n"
            "💡 Используйте кнопку 'Мои комнаты' чтобы войти в другую комнату.",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard() if is_user_admin else get_user_keyboard()
        )
        # Обновляем Reply клавиатуру
        await message.answer(
            "💡 <b>Главное меню</b>",
            parse_mode="HTML",
            reply_markup=get_reply_admin_keyboard() if is_user_admin else get_reply_user_keyboard()
        )
    else:
        await message.answer(
            "ℹ️ <b>Информация</b>\n\n"
            "😊 Вы не находитесь ни в одной комнате.\n\n"
            "💡 Используйте кнопку 'Мои комнаты' чтобы увидеть доступные комнаты.",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard() if is_user_admin else get_user_keyboard()
        )
        await message.answer(
            "💡 <b>Главное меню</b>",
            parse_mode="HTML",
            reply_markup=get_reply_admin_keyboard() if is_user_admin else get_reply_user_keyboard()
        )


@dp.message(Command("menu"))
async def cmd_menu(message: Message):
    """Показать главное меню"""
    user_id = message.from_user.id
    is_user_admin = await check_is_admin(user_id)
    
    if is_user_admin:
        text = (
            "🎉 <b>Главное меню</b>\n\n"
            "✨ Выберите действие из меню ниже:"
        )
        await message.answer(text, parse_mode="HTML", reply_markup=get_admin_keyboard())
    else:
        text = (
            "👋 <b>Главное меню</b>\n\n"
            "🎯 Выберите действие из меню ниже:"
        )
        await message.answer(text, parse_mode="HTML", reply_markup=get_user_keyboard())


@dp.message(lambda m: m.text in ["🏠 Создать комнату", "📂 Мои комнаты", "🌐 Все комнаты", 
                                 "➕ Добавить доступ", "➖ Удалить доступ", "🗑️ Удалить комнату",
                                 "👑 Управление ролями", "🚪 Выйти из комнаты", "🔙 Главное меню",
                                 "✏️ Изменить название", "➕ Добавить участника", "👥 Участники"])
async def handle_reply_buttons(message: Message):
    """Обработка нажатий на Reply кнопки"""
    user_id = message.from_user.id
    text = message.text
    is_user_admin = await check_is_admin(user_id)
    
    if text == "🏠 Создать комнату":
        if not is_user_admin:
            await message.answer("🚫 У вас нет прав для этого действия.", reply_markup=get_reply_user_keyboard())
            return
        await cmd_create_room(message)
    elif text == "📂 Мои комнаты":
        await cmd_my_rooms(message)
    elif text == "🌐 Все комнаты":
        if not is_user_admin:
            await message.answer("🚫 У вас нет прав для этого действия.", reply_markup=get_reply_user_keyboard())
            return
        await cmd_all_rooms(message)
    elif text == "➕ Добавить доступ":
        if not is_user_admin:
            await message.answer("🚫 У вас нет прав для этого действия.", reply_markup=get_reply_user_keyboard())
            return
        await cmd_add_access(message)
    elif text == "➖ Удалить доступ":
        if not is_user_admin:
            await message.answer("🚫 У вас нет прав для этого действия.", reply_markup=get_reply_user_keyboard())
            return
        await cmd_remove_access(message)
    elif text == "🗑️ Удалить комнату":
        if not is_user_admin:
            await message.answer("🚫 У вас нет прав для этого действия.", reply_markup=get_reply_user_keyboard())
            return
        await cmd_delete_room(message)
    elif text == "👑 Управление ролями":
        if not is_user_admin:
            await message.answer("🚫 У вас нет прав для этого действия.", reply_markup=get_reply_user_keyboard())
            return
        # Показываем меню управления ролями
        builder = InlineKeyboardBuilder()
        builder.button(text="👑 Администраторы", callback_data="role_list_admin")
        builder.button(text="👥 Клиенты", callback_data="role_list_customer")
        builder.button(text="👨‍💻 Разработчики", callback_data="role_list_developer")
        builder.button(text="👤 Все пользователи", callback_data="role_list_all")
        builder.button(text="➕ Добавить роль", callback_data="role_add_select")
        builder.button(text="🔙 Главное меню", callback_data="action_menu")
        builder.adjust(1, 1, 1, 1, 1, 1)
        
        # Получаем статистику по ролям
        admins = await db.get_users_by_role('admin')
        customers = await db.get_users_by_role('customer')
        developers = await db.get_users_by_role('developer')
        all_users = await db.get_all_users()
        
        text = "👑 <b>Управление ролями</b>\n\n"
        text += "📊 <b>Статистика:</b>\n"
        text += f"👑 Администраторы: <b>{len(admins)}</b>\n"
        text += f"👥 Клиенты: <b>{len(customers)}</b>\n"
        text += f"👨‍💻 Разработчики: <b>{len(developers)}</b>\n"
        text += f"👤 Всего пользователей: <b>{len(all_users)}</b>\n\n"
        text += "👇 Выберите действие:"
        
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    elif text == "🚪 Выйти из комнаты":
        await cmd_exit_room(message)
    elif text == "🔙 Главное меню":
        await cmd_menu(message)
    elif text == "✏️ Изменить название":
        if not is_user_admin:
            await message.answer("🚫 У вас нет прав для этого действия.", reply_markup=get_reply_user_keyboard())
            return
        if user_id not in user_active_rooms:
            await message.answer(
                "ℹ️ Вы не находитесь ни в одной комнате.",
                reply_markup=get_reply_admin_keyboard() if is_user_admin else get_reply_user_keyboard()
            )
            return
        room_id = user_active_rooms[user_id]
        await process_room_edit_text(message, room_id)
    elif text == "➕ Добавить участника":
        if not is_user_admin:
            await message.answer("🚫 У вас нет прав для этого действия.", reply_markup=get_reply_user_keyboard())
            return
        if user_id not in user_active_rooms:
            await message.answer(
                "ℹ️ Вы не находитесь ни в одной комнате.",
                reply_markup=get_reply_admin_keyboard() if is_user_admin else get_reply_user_keyboard()
            )
            return
        room_id = user_active_rooms[user_id]
        # Показываем выбор роли
        builder = InlineKeyboardBuilder()
        builder.button(text="👤 Заказчик", callback_data=f"room_role_{room_id}_customer")
        builder.button(text="👨‍💻 Разработчик", callback_data=f"room_role_{room_id}_developer")
        builder.adjust(2)
        await message.answer(
            "➕ <b>Добавление участника</b>\n\n"
            "👆 Выберите роль для нового участника:",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    elif text == "👥 Участники":
        if not is_user_admin:
            await message.answer("🚫 У вас нет прав для этого действия.", reply_markup=get_reply_user_keyboard())
            return
        if user_id not in user_active_rooms:
            await message.answer(
                "ℹ️ Вы не находитесь ни в одной комнате.",
                reply_markup=get_reply_admin_keyboard() if is_user_admin else get_reply_user_keyboard()
            )
            return
        room_id = user_active_rooms[user_id]
        await show_room_members_text(message, room_id)


async def process_room_edit_text(message: Message, room_id: int):
    """Обработка редактирования комнаты через текст"""
    room = await db.get_room(room_id)
    if not room:
        await message.answer("❌ Комната не найдена.")
        return
    
    user_action_state[message.from_user.id] = f'edit_room_{room_id}'
    await message.answer(
        f"✏️ <b>Редактирование комнаты</b>\n\n"
        f"🏠 Текущее название: <b>{room['room_name']}</b>\n\n"
        f"📝 Отправьте новое название комнаты:\n\n"
        f"❌ Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML",
        reply_markup=get_reply_room_keyboard()
    )


async def show_room_members_text(message: Message, room_id: int):
    """Показать участников комнаты через текст"""
    room = await db.get_room(room_id)
    if not room:
        await message.answer("❌ Комната не найдена.")
        return
    
    members = await db.get_room_members(room_id)
    
    text = f"👥 <b>УПРАВЛЕНИЕ УЧАСТНИКАМИ</b>\n\n"
    text += f"🏠 Комната: <b>{room['room_name']}</b>\n"
    text += f"🆔 ID: <code>{room_id}</code>\n"
    text += f"📊 Всего участников: <b>{len(members)}</b>\n\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    if members:
        for member in members:
            role_emoji = "👤" if member['access_type'] == 'customer' else "👨‍💻"
            role_name = "Заказчик" if member['access_type'] == 'customer' else "Разработчик"
            username = f"@{member['username']}" if member['username'] else "Без username"
            full_name = member['full_name'] if member['full_name'] else "Без имени"
            text += f"{role_emoji} <b>{role_name}</b>\n"
            text += f"   👤 {full_name}\n"
            text += f"   📱 {username}\n"
            text += f"   🆔 ID: <code>{member['user_id']}</code>\n"
            text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    else:
        text += "😔 Участников пока нет.\n\n"
    
    builder = InlineKeyboardBuilder()
    if members:
        for member in members:
            current_role = member['access_type']
            new_role = 'developer' if current_role == 'customer' else 'customer'
            role_text = "👨‍💻→👤" if current_role == 'developer' else "👤→👨‍💻"
            username_display = f"@{member['username']}" if member['username'] else f"ID:{member['user_id']}"
            builder.button(
                text=f"{role_text} {username_display}",
                callback_data=f"room_change_role_{room_id}_{member['user_id']}_{new_role}"
            )
            builder.button(
                text=f"❌ Удалить {username_display}",
                callback_data=f"room_remove_member_{room_id}_{member['user_id']}"
            )
        builder.adjust(1, 1)
        builder.button(text="➕ Добавить участника", callback_data=f"room_add_access_{room_id}")
        builder.button(text="🔙 К комнате", callback_data=f"room_{room_id}")
        builder.adjust(1)
    else:
        builder.button(text="➕ Добавить участника", callback_data=f"room_add_access_{room_id}")
        builder.button(text="🔙 К комнате", callback_data=f"room_{room_id}")
        builder.adjust(1)
    
    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await message.answer("💡 Используйте кнопки выше для управления участниками.", reply_markup=get_reply_room_keyboard())


@dp.message(Command("cancel"))
async def cmd_cancel(message: Message):
    """Отменить текущее действие"""
    user_id = message.from_user.id
    if user_id in user_action_state:
        action = user_action_state[user_id]
        del user_action_state[user_id]
        await message.answer(
            "❌ <b>Действие отменено</b>\n\n"
            "✅ Вы успешно отменили текущее действие.\n\n"
            "💡 Можете использовать другие команды.",
            parse_mode="HTML"
        )
    elif user_id in user_active_rooms:
        del user_active_rooms[user_id]
        await message.answer(
            "🚪 <b>Выход из комнаты</b>\n\n"
            "✅ Вы вышли из активной комнаты.",
            parse_mode="HTML"
        )
    elif user_id in room_access_state:
        del room_access_state[user_id]
        await message.answer(
            "❌ <b>Действие отменено</b>\n\n"
            "✅ Добавление доступа отменено.",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "ℹ️ <b>Информация</b>\n\n"
            "😊 Нет активных действий для отмены.",
            parse_mode="HTML"
        )


@dp.message()
async def process_message(message: Message):
    """Обработка всех сообщений"""
    user_id = message.from_user.id
    text = message.text or message.caption or ""
    
    # Обработка добавления доступа из комнаты (с выбором роли)
    if user_id in room_access_state and text.isdigit():
        try:
            access_data = room_access_state[user_id]
            room_id = access_data['room_id']
            role = access_data['role']
            target_user_id = int(text)
            
            room = await db.get_room(room_id)
            if not room:
                await message.answer(
                    f"❌ <b>Ошибка</b>\n\n"
                    f"🏠 Комната не найдена.",
                    parse_mode="HTML"
                )
                del room_access_state[user_id]
                return
            
            await db.add_room_access(room_id, target_user_id, role)
            
            # Если роль customer, добавляем в базу заказчиков и обновляем роль
            if role == 'customer':
                await db.update_user_role(target_user_id, 'customer')
                await db.add_or_update_customer(target_user_id)
            
            role_name = "Заказчик" if role == 'customer' else "Разработчик"
            
            # Уведомляем пользователя
            try:
                await bot.send_message(
                    target_user_id,
                    f"🎉 <b>Доступ предоставлен!</b>\n\n"
                    f"🏠 Вам предоставлен доступ к комнате: <b>{room['room_name']}</b>\n"
                    f"👤 Роль: <b>{role_name}</b>\n\n"
                    f"💬 Теперь вы можете общаться в этой комнате.\n\n"
                    f"📂 Используйте <code>/my_rooms</code> чтобы войти в комнату.",
                    parse_mode="HTML"
                )
            except:
                pass
            
            builder = InlineKeyboardBuilder()
            builder.button(text="🔙 К комнате", callback_data=f"room_{room_id}")
            builder.button(text="🔙 Главное меню", callback_data="action_menu")
            builder.adjust(1)
            
            await message.answer(
                f"➕ <b>Доступ предоставлен</b>\n\n"
                f"✅ Пользователь <code>{target_user_id}</code> добавлен в комнату '<b>{room['room_name']}</b>'.\n"
                f"👤 Роль: <b>{role_name}</b>\n\n"
                f"📨 Ему отправлено уведомление.",
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
            
            del room_access_state[user_id]
            return
        except Exception as e:
            await message.answer(
                f"❌ <b>Ошибка при добавлении доступа</b>\n\n"
                f"🔍 Детали: {str(e)}",
                parse_mode="HTML"
            )
            if user_id in room_access_state:
                del room_access_state[user_id]
            return
    
    # Обработка редактирования названия комнаты
    # Приоритет: если есть активное действие редактирования, обрабатываем его ДО отправки в комнату
    if user_id in user_action_state and user_action_state[user_id].startswith('edit_room_'):
        try:
            room_id = int(user_action_state[user_id].split('_')[2])
            new_name = text.strip()
            
            if not new_name:
                await message.answer(
                    "❌ <b>Ошибка</b>\n\n"
                    "📝 Название не может быть пустым.",
                    parse_mode="HTML"
                )
                return
            
            room = await db.get_room(room_id)
            if not room:
                await message.answer(
                    "❌ <b>Ошибка</b>\n\n"
                    "🏠 Комната не найдена.",
                    parse_mode="HTML"
                )
                del user_action_state[user_id]
                return
            
            await db.update_room_name(room_id, new_name)
            
            builder = InlineKeyboardBuilder()
            builder.button(text="🔙 К комнате", callback_data=f"room_{room_id}")
            builder.button(text="🔙 Главное меню", callback_data="action_menu")
            builder.adjust(1)
            
            await message.answer(
                f"✏️ <b>Комната отредактирована</b>\n\n"
                f"✅ Название комнаты изменено на: <b>{new_name}</b>",
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
            
            del user_action_state[user_id]
            return
        except Exception as e:
            await message.answer(
                f"❌ <b>Ошибка при редактировании</b>\n\n"
                f"🔍 Детали: {str(e)}",
                parse_mode="HTML"
            )
            if user_id in user_action_state:
                del user_action_state[user_id]
            return
    
    # Обработка команд администратора
    if await check_is_admin(user_id) or is_admin(user_id):
        action = user_action_state.get(user_id)
        
        # Обработка удаления комнаты
        if action == 'delete_room' and text.isdigit():
            try:
                room_id = int(text)
                room = await db.get_room(room_id)
                if not room:
                    await message.answer(
                        f"❌ <b>Ошибка</b>\n\n"
                        f"🏠 Комната с ID <code>{room_id}</code> не найдена.",
                        parse_mode="HTML"
                    )
                    if user_id in user_action_state:
                        del user_action_state[user_id]
                    return
                
                await db.delete_room(room_id)
                
                # Удаляем из активных комнат всех пользователей
                users_to_remove = [uid for uid, rid in user_active_rooms.items() if rid == room_id]
                for uid in users_to_remove:
                    del user_active_rooms[uid]
                
                await message.answer(
                    f"🗑️ <b>Комната удалена</b>\n\n"
                    f"✅ Комната '<b>{room['room_name']}</b>' (ID: {room_id}) успешно удалена.\n\n"
                    f"⚠️ Все сообщения и доступы к этой комнате были удалены.",
                    parse_mode="HTML",
                    reply_markup=get_back_to_menu_keyboard(True)
                )
                
                if user_id in user_action_state:
                    del user_action_state[user_id]
                return
            except Exception as e:
                await message.answer(
                    f"❌ <b>Ошибка при удалении комнаты</b>\n\n"
                    f"🔍 Детали: {str(e)}",
                    parse_mode="HTML"
                )
                if user_id in user_action_state:
                    del user_action_state[user_id]
                return
        
        # Обработка добавления роли
        if action and action.startswith('add_role_') and text.isdigit():
            try:
                role = action.split("_")[2]
                target_user_id = int(text)
                
                role_names = {
                    'admin': 'Администратор',
                    'customer': 'Клиент',
                    'developer': 'Разработчик',
                    'user': 'Пользователь'
                }
                
                role_emojis = {
                    'admin': '👑',
                    'customer': '👥',
                    'developer': '👨‍💻',
                    'user': '👤'
                }
                
                # Получаем текущую роль
                current_role = await db.get_user_role(target_user_id)
                
                # Обновляем роль
                await db.update_user_role(target_user_id, role)
                
                # Если роль изменена на "customer", автоматически добавляем в базу заказчиков
                if role == 'customer':
                    await db.add_or_update_customer(target_user_id)
                
                # Уведомляем пользователя
                role_name = role_names.get(role, 'Пользователь')
                role_emoji = role_emojis.get(role, '👤')
                
                try:
                    await bot.send_message(
                        target_user_id,
                        f"{role_emoji} <b>Роль изменена!</b>\n\n"
                        f"✨ Ваша роль в боте изменена на: <b>{role_name}</b>\n\n"
                        f"💡 Используйте <code>/start</code> чтобы увидеть доступные функции.",
                        parse_mode="HTML"
                    )
                except:
                    pass
                
                await message.answer(
                    f"✅ <b>Роль назначена</b>\n\n"
                    f"{role_emoji} Пользователь <code>{target_user_id}</code> теперь <b>{role_name}</b>.",
                    parse_mode="HTML",
                    reply_markup=get_back_to_menu_keyboard(True)
                )
                
                if user_id in user_action_state:
                    del user_action_state[user_id]
                return
            except Exception as e:
                await message.answer(
                    f"❌ <b>Ошибка при назначении роли</b>\n\n"
                    f"🔍 Детали: {str(e)}",
                    parse_mode="HTML"
                )
                if user_id in user_action_state:
                    del user_action_state[user_id]
                return
        
        # Обработка создания комнаты из чата
        action = user_action_state.get(user_id)
        if action and action.startswith('create_room_from_chat_') and text.strip():
            try:
                parts = action.split("_")
                target_user_id = int(parts[4])
                role = parts[5] if len(parts) > 5 else 'customer'  # По умолчанию заказчик
                room_name = text.strip()
                
                # Создаем комнату
                customer_id = target_user_id if role == 'customer' else None
                room_id = await db.create_room(room_name, user_id, customer_id)
                
                # Добавляем пользователя с нужной ролью
                await db.add_room_access(room_id, target_user_id, role)
                
                # Если роль customer, добавляем в базу заказчиков и обновляем роль в users
                if role == 'customer':
                    await db.update_user_role(target_user_id, 'customer')
                    await db.add_or_update_customer(target_user_id)
                
                # Уведомляем пользователя
                role_name = "Заказчик" if role == 'customer' else "Разработчик"
                try:
                    await bot.send_message(
                        target_user_id,
                        "🎉 <b>Новая комната создана!</b>\n\n"
                        f"🏠 Вам предоставлен доступ к комнате: <b>{room_name}</b>\n"
                        f"👤 Ваша роль: <b>{role_name}</b>\n\n"
                        "💬 Теперь вы можете общаться в этой комнате.\n\n"
                        "📂 Используйте <code>/start</code> или <code>/my_rooms</code> чтобы войти в комнату.",
                        parse_mode="HTML"
                    )
                except:
                    pass
                
                # Удаляем активный чат
                if user_id in admin_active_chats:
                    del admin_active_chats[user_id]
                
                await message.answer(
                    f"🎉 <b>Комната создана!</b>\n\n"
                    f"🏠 Название: <b>{room_name}</b>\n"
                    f"👤 Пользователь: <code>{target_user_id}</code>\n"
                    f"👤 Роль: <b>{role_name}</b>\n"
                    f"🆔 ID комнаты: <code>{room_id}</code>\n\n"
                    f"✅ Комната готова к использованию!",
                    parse_mode="HTML",
                    reply_markup=get_back_to_menu_keyboard(True)
                )
                
                if user_id in user_action_state:
                    del user_action_state[user_id]
                return
            except Exception as e:
                logger.error(f"Ошибка при создании комнаты из чата: {e}")
                await message.answer(
                    f"❌ <b>Ошибка</b>\n\n"
                    f"Не удалось создать комнату: {str(e)}",
                    parse_mode="HTML"
                )
                if user_id in user_action_state:
                    del user_action_state[user_id]
                return
        
        # Обработка добавления отзыва
        if action and action.startswith('add_review_'):
            try:
                room_id = int(action.split("_")[2])
                review_text = text.strip()
                
                if not review_text:
                    await message.answer(
                        "❌ <b>Ошибка</b>\n\n"
                        "📝 Отзыв не может быть пустым.\n\n"
                        "💬 Пожалуйста, отправьте ваш отзыв.",
                        parse_mode="HTML"
                    )
                    return
                
                # Добавляем отзыв
                review_id = await db.add_review(user_id, room_id, review_text)
                
                await message.answer(
                    "✅ <b>Отзыв добавлен!</b>\n\n"
                    f"⭐ Ваш отзыв успешно опубликован.\n\n"
                    f"💡 Спасибо за вашу обратную связь!",
                    parse_mode="HTML",
                    reply_markup=get_back_to_menu_keyboard(False)
                )
                
                if user_id in user_action_state:
                    del user_action_state[user_id]
                return
            except Exception as e:
                await message.answer(
                    f"❌ <b>Ошибка</b>\n\n"
                    f"Не удалось добавить отзыв: {str(e)}",
                    parse_mode="HTML"
                )
                if user_id in user_action_state:
                    del user_action_state[user_id]
                return
        
        # Обработка ответа на отзыв
        if action and action.startswith('review_reply_'):
            try:
                review_id = int(action.split("_")[2])
                reply_text = text.strip()
                
                if not reply_text:
                    await message.answer(
                        "❌ <b>Ошибка</b>\n\n"
                        "📝 Ответ не может быть пустым.\n\n"
                        "💬 Пожалуйста, отправьте ваш ответ.",
                        parse_mode="HTML"
                    )
                    return
                
                # Добавляем ответ
                await db.add_admin_reply(review_id, reply_text)
                
                # Получаем отзыв для уведомления автора
                review = await db.get_review(review_id)
                if review:
                    try:
                        await bot.send_message(
                            review['user_id'],
                            "👑 <b>Ответ на ваш отзыв</b>\n\n"
                            f"💬 Администратор ответил на ваш отзыв:\n\n"
                            f"{reply_text}",
                            parse_mode="HTML"
                        )
                    except:
                        pass
                
                await message.answer(
                    "✅ <b>Ответ добавлен!</b>\n\n"
                    f"👑 Ваш ответ на отзыв успешно опубликован.",
                    parse_mode="HTML",
                    reply_markup=get_back_to_menu_keyboard(True)
                )
                
                if user_id in user_action_state:
                    del user_action_state[user_id]
                return
            except Exception as e:
                await message.answer(
                    f"❌ <b>Ошибка</b>\n\n"
                    f"Не удалось добавить ответ: {str(e)}",
                    parse_mode="HTML"
                )
                if user_id in user_action_state:
                    del user_action_state[user_id]
                return
        
        # Обработка редактирования пометок
        if action and action.startswith('edit_notes_'):
            try:
                target_user_id = int(action.split("_")[2])
                notes = text.strip() if text.strip() else ""  # Разрешаем пустую строку для удаления
                await db.update_customer_notes(target_user_id, notes)
                
                if notes:
                    await message.answer(
                        f"✅ <b>Пометки обновлены</b>\n\n"
                        f"👤 Заказчик: <code>{target_user_id}</code>\n"
                        f"📝 Пометки сохранены.",
                        parse_mode="HTML",
                        reply_markup=get_back_to_menu_keyboard(True)
                    )
                else:
                    await message.answer(
                        f"🗑️ <b>Пометки удалены</b>\n\n"
                        f"👤 Заказчик: <code>{target_user_id}</code>\n"
                        f"📝 Пометки успешно удалены.",
                        parse_mode="HTML",
                        reply_markup=get_back_to_menu_keyboard(True)
                    )
                
                if user_id in user_action_state:
                    del user_action_state[user_id]
                return
            except Exception as e:
                await message.answer(
                    f"❌ <b>Ошибка</b>\n\n"
                    f"Не удалось обновить пометки: {str(e)}",
                    parse_mode="HTML"
                )
                if user_id in user_action_state:
                    del user_action_state[user_id]
                return
        
        # Обработка создания комнаты
        if action == 'create_room' and text.strip():
            try:
                # Проверяем, есть ли символ "|" и ID заказчика
                if "|" in text and len(text.split("|")) == 2:
                    parts = [p.strip() for p in text.split("|")]
                    room_name = parts[0]
                    customer_id_str = parts[1]
                    
                    # Если есть ID заказчика
                    if room_name and customer_id_str.isdigit():
                        customer_id = int(customer_id_str)
                        room_id = await db.create_room(room_name, user_id, customer_id)
                        
                        # Добавляем заказчика в базу заказчиков и обновляем роль
                        await db.update_user_role(customer_id, 'customer')
                        await db.add_or_update_customer(customer_id)
                        
                        # Уведомляем заказчика
                        try:
                            await bot.send_message(
                                customer_id,
                                "🎉 <b>Новая комната создана!</b>\n\n"
                                f"🏠 Вам предоставлен доступ к комнате: <b>{room_name}</b>\n\n"
                                "💬 Теперь вы можете общаться с разработчиками в этой комнате.\n\n"
                                "📂 Используйте <code>/my_rooms</code> чтобы войти в комнату.",
                                parse_mode="HTML"
                            )
                        except:
                            pass
                        
                        await message.answer(
                            f"🎉 <b>Комната создана!</b>\n\n"
                            f"🏠 Название: <b>{room_name}</b>\n"
                            f"🆔 ID: <code>{room_id}</code>\n"
                            f"👤 Заказчик: <code>{customer_id}</code>\n\n"
                            f"✅ Заказчик получил уведомление о создании комнаты.",
                            parse_mode="HTML",
                            reply_markup=get_back_to_menu_keyboard(True)
                        )
                    else:
                        await message.answer(
                            "❌ <b>Ошибка</b>\n\n"
                            "⚠️ Неверный формат. Используйте:\n"
                            "<code>Название | ID заказчика</code>\n\n"
                            "или просто:\n"
                            "<code>Название</code>",
                            parse_mode="HTML"
                        )
                        return
                else:
                    # Создаем комнату без заказчика
                    room_name = text.strip()
                    if room_name:
                        room_id = await db.create_room(room_name, user_id, None)
                        
                        await message.answer(
                            f"🎉 <b>Комната создана!</b>\n\n"
                            f"🏠 Название: <b>{room_name}</b>\n"
                            f"🆔 ID: <code>{room_id}</code>\n\n"
                            f"💡 Заказчика можно добавить позже через управление комнатой.",
                            parse_mode="HTML",
                            reply_markup=get_back_to_menu_keyboard(True)
                        )
                    else:
                        await message.answer(
                            "❌ <b>Ошибка</b>\n\n"
                            "⚠️ Название комнаты не может быть пустым.",
                            parse_mode="HTML"
                        )
                        return
                
                # Очищаем состояние
                if user_id in user_action_state:
                    del user_action_state[user_id]
                return
            except Exception as e:
                await message.answer(
                    f"❌ <b>Ошибка при создании комнаты</b>\n\n"
                    f"🔍 Детали: {str(e)}",
                    parse_mode="HTML"
                )
                if user_id in user_action_state:
                    del user_action_state[user_id]
                return
        
        # Обработка создания комнаты и управления доступом (старая логика для обратной совместимости)
        if "|" in text and len(text.split("|")) == 2:
            parts = [p.strip() for p in text.split("|")]
            
            # Добавление/удаление доступа: "ID комнаты | ID пользователя"
            if parts[0].isdigit() and parts[1].isdigit():
                try:
                    room_id = int(parts[0])
                    target_user_id = int(parts[1])
                    
                    # Проверяем существование комнаты
                    room = await db.get_room(room_id)
                    if not room:
                        await message.answer(
                            f"❌ <b>Ошибка</b>\n\n"
                            f"🏠 Комната с ID <code>{room_id}</code> не найдена.",
                            parse_mode="HTML"
                        )
                        if user_id in user_action_state:
                            del user_action_state[user_id]
                        return
                    
                    action = user_action_state.get(user_id, 'add_access')
                    
                    if action == 'remove_access':
                        # Удаление доступа
                        await db.remove_room_access(room_id, target_user_id)
                        
                        # Удаляем из активных комнат, если пользователь был в этой комнате
                        if target_user_id in user_active_rooms and user_active_rooms[target_user_id] == room_id:
                            del user_active_rooms[target_user_id]
                        
                        # Уведомляем пользователя
                        try:
                            await bot.send_message(
                                target_user_id,
                                f"🚫 <b>Доступ удален</b>\n\n"
                                f"❌ Вам был удален доступ к комнате: <b>{room['room_name']}</b>",
                                parse_mode="HTML"
                            )
                        except:
                            pass
                        
                        await message.answer(
                            f"➖ <b>Доступ удален</b>\n\n"
                            f"✅ Доступ к комнате '<b>{room['room_name']}</b>' удален у пользователя <code>{target_user_id}</code>.",
                            parse_mode="HTML",
                            reply_markup=get_back_to_menu_keyboard(True)
                        )
                    else:
                        # Добавление доступа
                        await db.add_room_access(room_id, target_user_id)
                        
                        # Уведомляем пользователя
                        try:
                            await bot.send_message(
                                target_user_id,
                                "🎉 <b>Доступ предоставлен!</b>\n\n"
                                f"🏠 Вам предоставлен доступ к комнате: <b>{room['room_name']}</b>\n\n"
                                "💬 Теперь вы можете общаться в этой комнате.\n\n"
                                "📂 Используйте <code>/my_rooms</code> чтобы войти в комнату.",
                                parse_mode="HTML"
                            )
                        except:
                            pass
                        
                        await message.answer(
                            f"➕ <b>Доступ предоставлен</b>\n\n"
                            f"✅ Доступ к комнате '<b>{room['room_name']}</b>' предоставлен пользователю <code>{target_user_id}</code>.",
                            parse_mode="HTML",
                            reply_markup=get_back_to_menu_keyboard(True)
                        )
                    
                    # Очищаем состояние
                    if user_id in user_action_state:
                        del user_action_state[user_id]
                    
                    return
                except Exception as e:
                    await message.answer(f"❌ Ошибка: {e}")
                    if user_id in user_action_state:
                        del user_action_state[user_id]
                    return
    
    # Обработка обычных сообщений в комнатах
    # НО только если нет активных действий управления и это не Reply кнопка
    reply_buttons_list = ["🏠 Создать комнату", "📂 Мои комнаты", "🌐 Все комнаты", 
                         "➕ Добавить доступ", "➖ Удалить доступ", "🗑️ Удалить комнату",
                         "👑 Управление ролями", "🚪 Выйти из комнаты", "🔙 Главное меню",
                         "✏️ Изменить название", "➕ Добавить участника", "👥 Участники"]
    
    if user_id in user_active_rooms and user_id not in user_action_state and user_id not in room_access_state and text not in reply_buttons_list:
        room_id = user_active_rooms[user_id]
        room = await db.get_room(room_id)
        
        if not room:
            await message.answer(
                "❌ <b>Ошибка</b>\n\n"
                "🏠 Комната не найдена. Возможно, она была удалена.\n\n"
                "💡 Используйте <code>/my_rooms</code> чтобы увидеть доступные комнаты.",
                parse_mode="HTML"
            )
            del user_active_rooms[user_id]
            return
        
        # Определяем, является ли пользователь заказчиком
        is_customer = (room['customer_id'] == user_id)
        
        # Формируем текст сообщения
        message_text = text
        if not message_text and message.caption:
            message_text = message.caption
        
        # Сохраняем сообщение (если есть текст)
        if message_text:
            await db.save_message(room_id, user_id, message_text, is_customer)
        
        # Получаем всех участников комнаты
        members = await db.get_room_members(room_id)
        
        # Формируем заголовок сообщения
        if is_customer:
            header = f"💬 <b>Сообщение из комнаты '{room['room_name']}':</b>\n\n"
        else:
            header = f"👨‍💻 <b>Разработчик в комнате '{room['room_name']}':</b>\n\n"
        
        # Отправляем сообщение всем участникам, кроме отправителя
        for member in members:
            if member['user_id'] != user_id:
                # Проверяем, находится ли пользователь в этой комнате
                is_member_in_room = (member['user_id'] in user_active_rooms and 
                                   user_active_rooms[member['user_id']] == room_id)
                
                # Проверяем, является ли участник администратором
                is_member_admin = await check_is_admin(member['user_id'])
                
                # Если пользователь не в комнате, проверяем настройки уведомлений
                notification_enabled = True  # По умолчанию включено
                if not is_member_in_room:
                    if is_member_admin:
                        # Для администраторов проверяем настройки уведомлений
                        notification_enabled = await db.get_room_notification(member['user_id'], room_id)
                        if not notification_enabled:
                            continue  # Пропускаем, если уведомления выключены
                    # Для разработчиков и клиентов уведомления всегда включены (notification_enabled = True)
                
                try:
                    # Отправляем медиа-файлы или текстовые сообщения
                    if message.photo:
                        # Фото
                        await bot.send_photo(
                            member['user_id'],
                            message.photo[-1].file_id,
                            caption=header + message_text if message_text else header.rstrip(),
                            parse_mode="HTML"
                        )
                    elif message.video:
                        # Видео
                        await bot.send_video(
                            member['user_id'],
                            message.video.file_id,
                            caption=header + message_text if message_text else header.rstrip(),
                            parse_mode="HTML"
                        )
                    elif message.document:
                        # Документ
                        await bot.send_document(
                            member['user_id'],
                            message.document.file_id,
                            caption=header + message_text if message_text else header.rstrip(),
                            parse_mode="HTML"
                        )
                    elif message.audio:
                        # Аудио
                        await bot.send_audio(
                            member['user_id'],
                            message.audio.file_id,
                            caption=header + message_text if message_text else header.rstrip(),
                            parse_mode="HTML"
                        )
                    elif message.voice:
                        # Голосовое сообщение
                        await bot.send_voice(
                            member['user_id'],
                            message.voice.file_id,
                            caption=header.rstrip() if not message_text else None,
                            parse_mode="HTML"
                        )
                    elif message.video_note:
                        # Видео-кружок
                        await bot.send_video_note(
                            member['user_id'],
                            message.video_note.file_id
                        )
                        if message_text:
                            await bot.send_message(
                                member['user_id'],
                                header + message_text,
                                parse_mode="HTML"
                            )
                    elif message.sticker:
                        # Стикер
                        await bot.send_sticker(
                            member['user_id'],
                            message.sticker.file_id
                        )
                        if message_text:
                            await bot.send_message(
                                member['user_id'],
                                header + message_text,
                                parse_mode="HTML"
                            )
                    elif message_text:
                        # Текстовое сообщение
                        await bot.send_message(
                            member['user_id'],
                            header + message_text,
                            parse_mode="HTML"
                        )
                    
                    # Если пользователь не в комнате, отправляем уведомление с названием комнаты
                    if not is_member_in_room:
                        # notification_enabled уже проверено выше для администраторов
                        # Для разработчиков и клиентов всегда отправляем уведомление
                        notification_text = (
                            f"🔔 <b>Новое сообщение в комнате</b>\n\n"
                            f"🏠 <b>Комната:</b> {room['room_name']}\n"
                            f"💬 Используйте <code>/my_rooms</code> чтобы войти в комнату."
                        )
                        try:
                            await bot.send_message(
                                member['user_id'],
                                notification_text,
                                parse_mode="HTML"
                            )
                        except Exception as e:
                            logger.error(f"Ошибка отправки уведомления пользователю {member['user_id']}: {e}")
                except Exception as e:
                    logger.error(f"Ошибка отправки сообщения пользователю {member['user_id']}: {e}")
        
        # Подтверждение отправителю
        if is_customer:
            await message.answer(
                "✅ <b>Сообщение отправлено</b>\n\n"
                "👨‍💻 Ваше сообщение доставлено разработчикам.",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "✅ <b>Сообщение отправлено</b>\n\n"
                "💬 Ваше сообщение доставлено в комнату.",
                parse_mode="HTML"
            )
    else:
        # Пользователь не в комнате
        is_user_admin = await check_is_admin(user_id) or is_admin(user_id)
        
        if is_user_admin:
            # Администратор может отвечать в активном чате
            if user_id in admin_active_chats:
                chat_id = admin_active_chats[user_id]
                chat = await db.get_chat_by_chat_id(chat_id)
                if chat:
                    target_user_id = chat['user_id']
                    
                    # Формируем текст сообщения
                    message_text = text
                    if not message_text and message.caption:
                        message_text = message.caption
                    
                    # Сохраняем сообщение в чат
                    if message_text:
                        await db.save_chat_message(chat_id, user_id, message_text, False)
                    
                    # Отправляем сообщение пользователю
                    header = "💬 <b>Ответ от администратора:</b>\n\n"
                    try:
                        if message.photo:
                            await bot.send_photo(
                                target_user_id,
                                message.photo[-1].file_id,
                                caption=header + message_text if message_text else header.rstrip(),
                                parse_mode="HTML"
                            )
                        elif message.video:
                            await bot.send_video(
                                target_user_id,
                                message.video.file_id,
                                caption=header + message_text if message_text else header.rstrip(),
                                parse_mode="HTML"
                            )
                        elif message.document:
                            await bot.send_document(
                                target_user_id,
                                message.document.file_id,
                                caption=header + message_text if message_text else header.rstrip(),
                                parse_mode="HTML"
                            )
                        elif message.audio:
                            await bot.send_audio(
                                target_user_id,
                                message.audio.file_id,
                                caption=header + message_text if message_text else header.rstrip(),
                                parse_mode="HTML"
                            )
                        elif message.voice:
                            await bot.send_voice(
                                target_user_id,
                                message.voice.file_id,
                                caption=header.rstrip() if not message_text else None,
                                parse_mode="HTML"
                            )
                        elif message.video_note:
                            await bot.send_video_note(
                                target_user_id,
                                message.video_note.file_id
                            )
                            if message_text:
                                await bot.send_message(
                                    target_user_id,
                                    header + message_text,
                                    parse_mode="HTML"
                                )
                        elif message.sticker:
                            await bot.send_sticker(
                                target_user_id,
                                message.sticker.file_id
                            )
                            if message_text:
                                await bot.send_message(
                                    target_user_id,
                                    header + message_text,
                                    parse_mode="HTML"
                                )
                        else:
                            await bot.send_message(
                                target_user_id,
                                header + message_text,
                                parse_mode="HTML"
                            )
                        
                        # Убираем подтверждение отправки в чате
                        # await message.answer(
                        #     "✅ <b>Сообщение отправлено</b>\n\n"
                        #     "💬 Ваш ответ доставлен пользователю.",
                        #     parse_mode="HTML"
                        # )
                    except Exception as e:
                        await message.answer(
                            f"❌ <b>Ошибка отправки</b>\n\n"
                            f"Не удалось отправить сообщение: {str(e)}",
                            parse_mode="HTML"
                        )
                    return
                else:
                    await message.answer(
                        "ℹ️ <b>Информация</b>\n\n"
                        "😊 Вы не находитесь ни в одной комнате.\n\n"
                        "💡 Используйте <code>/my_rooms</code> или кнопку 'Чаты' чтобы начать работу.",
                        parse_mode="HTML"
                    )
            else:
                await message.answer(
                    "ℹ️ <b>Информация</b>\n\n"
                    "😊 Вы не находитесь ни в одной комнате.\n\n"
                    "💡 Используйте <code>/my_rooms</code> или кнопку 'Чаты' чтобы начать работу.",
                    parse_mode="HTML"
                )
        else:
            # Обычный пользователь пишет в чат
            # Сначала убеждаемся, что пользователь добавлен в базу
            username = message.from_user.username
            full_name = message.from_user.full_name
            is_user_admin = await check_is_admin(user_id)
            role = 'admin' if is_user_admin else 'user'
            await db.add_user(user_id, username, full_name, role)
            
            # Создаем или получаем чат
            chat_id = await db.get_or_create_chat(user_id)
            
            # Формируем текст сообщения
            message_text = text
            if not message_text and message.caption:
                message_text = message.caption
            
            # Сохраняем сообщение в чат
            if message_text:
                await db.save_chat_message(chat_id, user_id, message_text, True)
            
            # Добавляем в базу заказчиков всех, кто пишет, кроме админов и разработчиков
            user_role = await db.get_user_role(user_id)
            # Добавляем если не админ и не разработчик
            if not is_user_admin and user_role != 'developer':
                await db.add_or_update_customer(user_id)
            
            # Отправляем сообщение всем администраторам
            header = f"💬 <b>Новое сообщение от пользователя:</b>\n\n"
            user_info = f"👤 <b>Пользователь:</b> {message.from_user.full_name or 'Без имени'}\n"
            if message.from_user.username:
                user_info += f"📱 <b>Username:</b> @{message.from_user.username}\n"
            user_info += f"🆔 <b>ID:</b> <code>{user_id}</code>\n\n"
            
            for admin_id in ADMIN_IDS:
                try:
                    if message.photo:
                        await bot.send_photo(
                            admin_id,
                            message.photo[-1].file_id,
                            caption=header + user_info + message_text if message_text else header + user_info.rstrip(),
                            parse_mode="HTML"
                        )
                    elif message.video:
                        await bot.send_video(
                            admin_id,
                            message.video.file_id,
                            caption=header + user_info + message_text if message_text else header + user_info.rstrip(),
                            parse_mode="HTML"
                        )
                    elif message.document:
                        await bot.send_document(
                            admin_id,
                            message.document.file_id,
                            caption=header + user_info + message_text if message_text else header + user_info.rstrip(),
                            parse_mode="HTML"
                        )
                    elif message.audio:
                        await bot.send_audio(
                            admin_id,
                            message.audio.file_id,
                            caption=header + user_info + message_text if message_text else header + user_info.rstrip(),
                            parse_mode="HTML"
                        )
                    elif message.voice:
                        await bot.send_voice(
                            admin_id,
                            message.voice.file_id,
                            caption=header.rstrip() if not message_text else None,
                            parse_mode="HTML"
                        )
                        if message_text:
                            await bot.send_message(
                                admin_id,
                                header + user_info + message_text,
                                parse_mode="HTML"
                            )
                    elif message.video_note:
                        await bot.send_video_note(
                            admin_id,
                            message.video_note.file_id
                        )
                        if message_text:
                            await bot.send_message(
                                admin_id,
                                header + user_info + message_text,
                                parse_mode="HTML"
                            )
                    elif message.sticker:
                        await bot.send_sticker(
                            admin_id,
                            message.sticker.file_id
                        )
                        if message_text:
                            await bot.send_message(
                                admin_id,
                                header + user_info + message_text,
                                parse_mode="HTML"
                            )
                    else:
                        await bot.send_message(
                            admin_id,
                            header + user_info + message_text,
                            parse_mode="HTML"
                        )
                except Exception as e:
                    logger.error(f"Ошибка отправки сообщения администратору {admin_id}: {e}")
            
            # Подтверждение пользователю
            await message.answer(
                "✅ <b>Сообщение получено</b>\n\n"
                "💬 Ваше сообщение доставлено администраторам.\n"
                "⏳ Мы свяжемся с вами в ближайшее время.",
                parse_mode="HTML"
            )


async def main():
    """Главная функция запуска бота"""
    # Инициализация базы данных
    await db.init_db()
    
    # Устанавливаем админов в базе
    for admin_id in ADMIN_IDS:
        await set_user_admin(admin_id)
    
    logger.info("Бот запущен!")
    
    # Запуск бота
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

