import asyncio
import logging
import pickle
import os
import json
from dataclasses import dataclass
from typing import Optional, Dict

from telethon import TelegramClient, events
from telethon.tl.types import PeerUser, PeerChat, PeerChannel
from telethon.errors import RPCError

from dsk.api import DeepSeekAPI, AuthenticationError, RateLimitError, NetworkError, APIError

# ----------------- НАСТРОЙКИ -----------------
with open("config.json", "r", encoding="utf-8") as file:
    config = json.load(file)

API_ID            = config['api_id']
API_HASH          = config['api_hash']
SESSION           = config['session_name']
DEEPSEEK_KEY      = config['deepseek_token']
SYSTEM_PROMPT     = config['system_promt']
DEBOUNCE_SECONDS  = config['debounce_seconds']
INACTIVITY_SECONDS = config.get('inactivity_seconds')

USERS_PICKLE = "users.pickle"

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("telethon-user-deepseek")

# --------------- DeepSeek init ----------------
api = DeepSeekAPI(DEEPSEEK_KEY)

# ----------------- МОДЕЛИ ---------------------
@dataclass
class UserState:
    session_id: Optional[str] = None
    next_parent_id: Optional[str] = None
    is_waiting: bool = False
    buffer: str = ""
    debounce_task: Optional[asyncio.Task] = None
    inactivity_task: Optional[asyncio.Task] = None  # <--- НОВОЕ

# user_id -> UserState
users: Dict[int, UserState] = {}

def load_users():
    global users
    if os.path.exists(USERS_PICKLE):
        try:
            with open(USERS_PICKLE, "rb") as f:
                users = pickle.load(f)
                logger.info("Users loaded from pickle: %d", len(users))
        except Exception:
            logger.warning("Failed to load users.pickle, starting fresh.")
            users = {}
    else:
        users = {}

def save_users():
    # ВАЖНО: сохраняем только когда в стейте нет активных asyncio.Task
    # (в этом коде мы всегда зануляем их перед save_users())
    try:
        with open(USERS_PICKLE, "wb") as f:
            pickle.dump(users, f)
    except Exception as e:
        logger.error("Failed to save users: %s", e)

# --------------- УТИЛИТЫ ----------------------
def format_recommendations(text: str) -> str:
    lines = text.split("\n")
    formatted = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if "—" in line:
            author, title = line.split("—", 1)
            formatted.append(f"<b>{author.strip()}</b> — {title.strip()}")
        else:
            formatted.append(line)
    formatted_text = "\n".join(formatted)
    formatted_text = formatted_text.replace("*", "")
    return formatted_text

def get_peer_id(event) -> int:
    peer = event.message.peer_id
    if isinstance(peer, PeerUser):
        return peer.user_id
    if isinstance(peer, PeerChat):
        return -peer.chat_id
    if isinstance(peer, PeerChannel):
        return -peer.channel_id
    if event.message.from_id and hasattr(event.message.from_id, "user_id"):
        return event.message.from_id.user_id
    return event.sender_id

async def send_typing(client: TelegramClient, entity):
    try:
        pass
        # await client.send_chat_action(entity, "typing")
    except RPCError:
        pass

# --------- НУДЖ ПРИ БЕЗОТВЕТЕ (5 МИН) --------
async def inactivity_nudge(client: TelegramClient, entity, user_id: int):
    """
    Ждём INACTIVITY_SECONDS после НАШЕГО ответа.
    Если за это время не пришло новое входящее — отправляем "Ты еще тут".
    Задача отменяется в обработчике при любом новом входящем сообщении.
    """
    state = users[user_id]
    try:
        await asyncio.sleep(INACTIVITY_SECONDS)
        # Если таск не отменили — значит входящих не было
        await client.send_message(entity, "Ты еще тут")
    except asyncio.CancelledError:
        # тишина — таск отменили из хэндлера, всё ок
        return
    finally:
        # аккуратно зануляем ссылку и сохраняем состояние
        state.inactivity_task = None
        save_users()

# ----------------- ДЕБАУНС -------------------
async def debounce_and_reply(client: TelegramClient, entity, user_id: int):
    """
    Ждем DEBOUNCE_SECONDS без новых сообщений, затем отправляем в DeepSeek.
    После отправки ответа ставим таймер безответа на INACTIVITY_SECONDS.
    """
    state = users[user_id]
    try:
        await asyncio.sleep(DEBOUNCE_SECONDS)

        if not state.buffer.strip():
            state.is_waiting = False
            return

        await send_typing(client, entity)

        if not state.session_id:
            session_id = api.create_chat_session()
            init_resp = api.chat_completion(session_id, SYSTEM_PROMPT) if SYSTEM_PROMPT else {"next_parent_id": None}
            state.session_id = session_id
            state.next_parent_id = init_resp.get("next_parent_id")
            # тут дебаунс таск ещё активен, не сохраняем (в pickle не должны попадать Task-объекты)

        try:
            response = api.chat_completion(
                state.session_id,
                state.buffer.strip(),
                state.next_parent_id
            )
        except (AuthenticationError, RateLimitError, NetworkError, APIError) as e:
            logger.error("DeepSeek error: %s", e)
            await client.send_message(entity, "❌ Ошибка при обращении к модели. Попробуйте позже.")
            state.is_waiting = False
            state.buffer = ""
            return

        if not response or "content" not in response:
            await client.send_message(entity, "❌ API вернул пустой ответ.")
            state.is_waiting = False
            state.buffer = ""
            return

        state.next_parent_id = response.get("next_parent_id")
        text = format_recommendations(response["content"])
        await client.send_message(entity, text, parse_mode="html")

        # ---- ПОСЛЕ НАШЕГО ОТВЕТА: СТАВИМ НУДЖ-ТАЙМЕР ----
        # если уже был активный — отменяем и ставим заново
        if state.inactivity_task is not None:
            state.inactivity_task.cancel()
            state.inactivity_task = None

        state.inactivity_task = asyncio.create_task(inactivity_nudge(client, entity, user_id))

    finally:
        # завершаем дебаунс
        state.is_waiting = False
        state.buffer = ""
        state.debounce_task = None
        # В ЭТОТ МОМЕНТ inactivity_task МОЖЕТ быть активным — НЕ сохраняем таск в pickle!
        # Поэтому сохраняем только когда обе задачи None.
        if state.inactivity_task is None and state.debounce_task is None:
            save_users()

# --------------- TELETHON ЛОГИКА --------------
async def main():
    load_users()

    client = TelegramClient(SESSION, API_ID, API_HASH,
                            system_version='4.16.30-vxCUSTOM',
                            auto_reconnect=True,   
                            connection_retries=5,  
                            request_retries=5, 
                            timeout=120,
                            # sequential_updates=True,
                            # receive_updates=False,
                            )
    
    await client.start()
    me = await client.get_me()
    logger.info("Logged in as %s", me.username or me.id)

    @client.on(events.NewMessage(incoming=True))
    async def handler(event: events.NewMessage.Event):
        # игнорируем собственные исходящие, чтобы не было триггера от наших сообщений
        if event.out: return

        user_id = get_peer_id(event)
        
        if user_id != 253848239: return
        
        entity = await event.get_input_chat()

        # гарантируем стейт
        if user_id not in users:
            users[user_id] = UserState()

        state = users[user_id]

        # Любое НОВОЕ входящее сообщение — отменяем нудж-таймер (юзер на связи)
        if state.inactivity_task is not None:
            state.inactivity_task.cancel()
            state.inactivity_task = None
            # не сохраняем, чтобы не пытаться сериализовать таски

        # добавляем текст в буфер для дебаунса
        msg_text = event.raw_text or ""
        state.buffer += (("\n" if state.buffer else "") + msg_text)

        # запускаем дебаунс-ответ, если не запущен
        if state.debounce_task is None:
            state.is_waiting = True
            state.debounce_task = asyncio.create_task(debounce_and_reply(client, entity, user_id))
        # иначе — дебаунс уже тикает, просто пополняем буфер

        # сохраняем только когда обе задачи None (здесь обычно есть активный дебаунс)
        # поэтому сохранение пропускаем

    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped by user")
