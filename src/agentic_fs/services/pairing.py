import logging

from agentic_fs.utils.ids import generate_file_id
from agentic_fs.services.file_store import FileStore

logger = logging.getLogger(__name__)


class PairingService:
    def __init__(self, file_store: FileStore):
        self.file_store = file_store

    def create_pairing(self, tenant: str, binary_file_id: str, extracted_text: str) -> str:
        """Create a pairing between a binary file and its extracted text.
        Returns the pairing_id."""
        pairing_id = generate_file_id()

        # Update the binary file's metadata with the pairing info
        self.file_store.update_metadata(
            tenant,
            binary_file_id,
            pairing_id=pairing_id,
            extracted_text_path=f"extracted:{binary_file_id}",
        )

        logger.info(f"Created pairing {pairing_id} for binary file {binary_file_id}")
        return pairing_id

    def link_files(self, tenant: str, file_id_a: str, file_id_b: str) -> str:
        """Manually link two files with a pairing_id."""
        pairing_id = generate_file_id()

        self.file_store.update_metadata(
            tenant, file_id_a, pairing_id=pairing_id, paired_file_id=file_id_b
        )
        self.file_store.update_metadata(
            tenant, file_id_b, pairing_id=pairing_id, paired_file_id=file_id_a
        )

        logger.info(f"Linked files {file_id_a} <-> {file_id_b} with pairing {pairing_id}")
        return pairing_id
