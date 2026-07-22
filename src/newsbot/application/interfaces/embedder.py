from typing import Protocol

from newsbot.domain.value_objects import EmbeddingVector


class Embedder(Protocol):
    def embed(self, text: str) -> EmbeddingVector: ...

    def embed_batch(self, texts: list[str]) -> list[EmbeddingVector]: ...
