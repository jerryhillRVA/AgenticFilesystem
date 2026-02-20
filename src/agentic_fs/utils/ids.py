import uuid

NAMESPACE_AGENTIC_FS = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def generate_file_id() -> str:
    return str(uuid.uuid4())


def deterministic_point_id(file_id: str, chunk_idx: int) -> str:
    return str(uuid.uuid5(NAMESPACE_AGENTIC_FS, f"{file_id}:{chunk_idx}"))
