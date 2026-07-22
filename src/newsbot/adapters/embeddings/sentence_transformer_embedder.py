from sentence_transformers import SentenceTransformer

from newsbot.domain.value_objects import EmbeddingVector


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        self._model = SentenceTransformer(model_name)

    def embed(self, text: str) -> EmbeddingVector:
        return self._model.encode(text, normalize_embeddings=True).tolist()

    def embed_batch(self, texts: list[str]) -> list[EmbeddingVector]:
        return self._model.encode(texts, normalize_embeddings=True).tolist()
