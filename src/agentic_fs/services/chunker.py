import tiktoken

from agentic_fs.config import settings


class Chunk:
    def __init__(
        self,
        text: str,
        chunk_idx: int,
        start_char: int,
        end_char: int,
        token_count: int,
    ):
        self.text = text
        self.chunk_idx = chunk_idx
        self.start_char = start_char
        self.end_char = end_char
        self.token_count = token_count


class Chunker:
    def __init__(self):
        self.chunk_size = settings.chunk_size_tokens
        self.overlap = max(1, int(self.chunk_size * settings.chunk_overlap_percent / 100))
        self.encoding = tiktoken.get_encoding("cl100k_base")

    def chunk(self, text: str) -> list[Chunk]:
        if not text or not text.strip():
            return []

        tokens = self.encoding.encode(text)
        total_tokens = len(tokens)

        if total_tokens <= self.chunk_size:
            return [
                Chunk(
                    text=text,
                    chunk_idx=0,
                    start_char=0,
                    end_char=len(text),
                    token_count=total_tokens,
                )
            ]

        chunks = []
        start = 0
        chunk_idx = 0

        while start < total_tokens:
            end = min(start + self.chunk_size, total_tokens)
            chunk_tokens = tokens[start:end]
            chunk_text = self.encoding.decode(chunk_tokens)

            # Calculate character offsets
            prefix_text = self.encoding.decode(tokens[:start])
            start_char = len(prefix_text)
            end_char = start_char + len(chunk_text)

            chunks.append(
                Chunk(
                    text=chunk_text,
                    chunk_idx=chunk_idx,
                    start_char=start_char,
                    end_char=end_char,
                    token_count=len(chunk_tokens),
                )
            )

            if end >= total_tokens:
                break

            start = end - self.overlap
            chunk_idx += 1

        return chunks
