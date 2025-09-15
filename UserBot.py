import logging, pickle, os, asyncio, random
from dataclasses import dataclass
from typing import Optional, Dict

from telethon import TelegramClient, events
from telethon.tl.types import PeerUser, PeerChat, PeerChannel

from ai.DeepSeek import DeepSeek
from crm.AmoCRM import AmoCRM

USERS_PICKLE = "users.pickle"

NUDGE_LIST = [
    "Можем продолжить?",
    "Правильно понимаю, что можем двигаться дальше?",
    "Еще актуально?",
    "Xnj-то не понравилось?",
]

@dataclass
class UserState:
    session_id: Optional[str] = None
    next_parent_id: Optional[str] = None
    buffer: str = ""
    debounce_task: Optional[asyncio.Task] = None
    inactivity_task: Optional[asyncio.Task] = None

class UserBot():
    def __init__(self, logger: logging, api_id: int, api_hash: str, session: str, debounce_seconds: int, inactivity_seconds: int, ai, crm):
        self.logger = logger
        self.users: Dict[int, UserState] = {} # user_id -> UserState
        self.client = TelegramClient(
            session,
            api_id,
            api_hash,
            system_version='4.16.30-vxCUSTOM',
            auto_reconnect=True,
            connection_retries=5,
            request_retries=5,
            timeout=120,
        )
        self.debounce_seconds = debounce_seconds
        self.inactivity_seconds = inactivity_seconds
        self.ai: DeepSeek = ai
        self.crm: AmoCRM = crm
        self.load_users()

    def load_users(self):
        if os.path.exists(USERS_PICKLE):
            try:
                with open(USERS_PICKLE, "rb") as f:
                    users = pickle.load(f)
                    self.logger.info("[UserBot] Users loaded from pickle: %d", len(users))
            except Exception as e:
                self.logger.error("[UserBot] Error loading user state from pickle: %s", e)
                users = {}
        else:
            self.logger.info("[UserBot] State not found.")
            users = {}

    def save_users(self):
        try:
            with open(USERS_PICKLE, "wb") as f:
                pickle.dump(self.users, f)
        except Exception as e:
            self.logger.error("[UserBot] Failed to save users: %s", e)

    def format_recommendations(self, text: str) -> str:
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

    def get_peer_id(self, event) -> int:
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

    async def inactivity_nudge(self, entity, user_id: int):
        """
        Ждём INACTIVITY_SECONDS после НАШЕГО ответа.
        Если за это время не пришло новое входящее — отправляем "Ты еще тут".
        Задача отменяется в обработчике при любом новом входящем сообщении.
        """
        state = self.users[user_id]
        try:
            await asyncio.sleep(self.inactivity_seconds)
            await self.client.send_message(entity, random.choice(NUDGE_LIST))
        except asyncio.CancelledError:
            return
        finally:
            state.inactivity_task = None

    # ----------------- ДЕБАУНС -------------------
    async def debounce_and_reply(self, entity: PeerUser, user_id: int):
        """
        Ждем DEBOUNCE_SECONDS без новых сообщений, затем отправляем в ии.
        После отправки ответа ставим таймер безответа на INACTIVITY_SECONDS если в нашем ответе был ?.
        """
        state = self.users[user_id]
        try:
            await asyncio.sleep(self.debounce_seconds)

            if not state.buffer.strip(): return

            # TODO: typing

            if not state.session_id:
                state.session_id, state.next_parent_id = await self.ai.create_thread()
                self.crm.create_task(
                    user_id,
                )

            response = {}
            is_error = False
            for i in range(3):
                self.logger.info(f"[UserBot][{state.session_id}] Attempt {i+1} of {3} to send message '{state.buffer.strip()}' to {entity} in session {state.session_id} with parent {state.next_parent_id}")
                try:
                    response = self.ai.send(state.buffer.strip(), state.session_id, state.next_parent_id)
                    self.logger.info(f"[UserBot][{state.session_id}] Response: {response}")
                
                except Exception as e:
                    self.logger.exception(f"[UserBot][{state.session_id}] Error: {str(e)})")
                    self.crm.update_task(entity.user_id, status_name="error")
                    is_error = True
                    continue

                if not response or "content" not in response:
                    self.logger.warning(f"[UserBot][{state.session_id}] Respounse is empty")
                    continue
                    
            if not response:
                self.logger.error(f"[UserBot] AI is not response")
                self.crm.update_task(entity.user_id, status_name="error")
                state.buffer = ""
                return
                
            if is_error:
                self.crm.update_task(entity.user_id, status_name="error")
                
            state.next_parent_id = response.get("next_parent_id")
            text = self.format_recommendations(response["content"])
            await self.client.send_message(entity, text, parse_mode="html")
            self.crm.update_task(entity.user_id, status_name="midle")

            if state.inactivity_task is not None:
                state.inactivity_task.cancel()
                state.inactivity_task = None

            if "?" in text:
                state.inactivity_task = asyncio.create_task(self.inactivity_nudge(entity, user_id))

        finally:
            state.buffer = ""
            state.debounce_task = None
            
            if state.inactivity_task is None and state.debounce_task is None:
                self.save_users()
                
    async def start(self):
        await self.client.start()
        me = await self.client.get_me()
        self.logger.info("Logged in as %s", me.username or me.id)

        @self.client.on(events.NewMessage(incoming=True))
        async def handler(event: events.NewMessage.Event):
            if event.out: return

            user_id = self.get_peer_id(event)
            
            # TODO: убрать защиту для вовы
            if user_id != 253848239 or user_id < 0: return
            
            entity = await event.get_input_chat()

            if user_id not in self.users:
                self.users[user_id] = UserState()

            state = self.users[user_id]

            if state.inactivity_task is not None:
                state.inactivity_task.cancel()
                state.inactivity_task = None

            msg_text = event.raw_text or ""
            state.buffer += (("\n" if state.buffer else "") + msg_text)

            if state.debounce_task is None:
                state.debounce_task = asyncio.create_task(self.debounce_and_reply(entity, user_id))

        await self.client.run_until_disconnected()