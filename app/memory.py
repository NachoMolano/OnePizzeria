import logging
from supabase import Client
from langchain.memory import ConversationSummaryBufferMemory
from datetime import datetime
from pydantic import PrivateAttr

logger = logging.getLogger(__name__)

class PersistedBufferMemory(ConversationSummaryBufferMemory):
    _client: Client = PrivateAttr()

    def __init__(
        self,
        supabase_client: Client,
        llm,
        memory_key: str = "summary",
        input_key: str = "input",
        output_key: str = "output",
        max_token_limit: int | None = None,
    ):
        super().__init__(
            llm=llm,
            memory_key=memory_key,
            input_key=input_key,
            output_key=output_key,
            max_token_limit=max_token_limit,
        )
        self._client = supabase_client

    def load_memory_variables(self, inputs: dict) -> dict:
        user = inputs.get("user_id")
        if not user:
            raise ValueError("El campo 'user_id' es obligatorio en inputs.")
        try:
            resp = (
                self._client.table("chat_memory")
                .select("value")
                .eq("user_id", user)
                .eq("key", self.memory_key)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            data = resp.data
            if data:
                self._buffer = data[0]["value"]
            else:
                self._buffer = ""
            logger.info(f"Loaded memory for user {user}: {self._buffer}")
        except Exception as e:
            self._buffer = ""
            logger.error("Error loading memory for user %s: %s", user, e, exc_info=True)
        return super().load_memory_variables(inputs)

    def save_context(self, inputs: dict, outputs: dict) -> None:
        super().save_context(inputs, outputs)
        self._buffer = self.moving_summary_buffer
        user = inputs.get("user_id")
        if not user:
            raise ValueError("El campo 'user_id' es obligatorio en inputs.")
        payload = {
            "user_id": user,
            "key": self.memory_key,
            "value": self._buffer,
            "created_at": datetime.utcnow().isoformat(),
        }
        logger.info(f"Saving payload to Supabase: {payload}")
        try:
            self._client.table("chat_memory").insert(payload).execute()
        except Exception as e:
            logger.error("Error saving context for user %s: %s", user, e, exc_info=True)