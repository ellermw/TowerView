from typing import List, Optional
from sqlalchemy.orm import Session
from ..models.server import Server
from ..models.credential import Credential
from ..schemas.server import ServerCreate, ServerUpdate
from ..core.encryption import credential_encryption


class ServerService:
    def __init__(self, db: Session):
        self.db = db

    def get_server_by_id(self, server_id: int) -> Optional[Server]:
        return self.db.query(Server).filter(Server.id == server_id).first()

    def get_servers_by_owner(self, owner_id: int) -> List[Server]:
        return self.db.query(Server).filter(Server.owner_id == owner_id).all()

    def get_enabled_servers(self) -> List[Server]:
        return self.db.query(Server).filter(Server.enabled == True).all()

    def create_server(self, server_data: ServerCreate, owner_id: int) -> Server:
        # Create the server
        server_dict = server_data.dict()
        credentials = server_dict.pop("credentials")

        server = Server(
            **server_dict,
            owner_id=owner_id
        )
        self.db.add(server)
        self.db.flush()  # Get the server ID

        # Encrypt and store credentials
        encrypted_credentials = credential_encryption.encrypt_credentials(credentials)
        credential = Credential(
            server_id=server.id,
            encrypted_payload=encrypted_credentials,
            auth_type="api_key"  # Default, can be updated based on provider
        )
        self.db.add(credential)

        self.db.commit()
        self.db.refresh(server)
        return server

    def get_server_credentials(self, server_id: int) -> Optional[dict]:
        credential = self.db.query(Credential).filter(
            Credential.server_id == server_id
        ).first()

        if not credential:
            return None

        return credential_encryption.decrypt_credentials(credential.encrypted_payload)

    def update_server_last_seen(self, server_id: int):
        server = self.get_server_by_id(server_id)
        if server:
            from datetime import datetime
            server.last_seen_at = datetime.utcnow()
            self.db.commit()

    def update_server(self, server_id: int, server_data: ServerUpdate) -> Server:
        server = self.get_server_by_id(server_id)
        if not server:
            raise ValueError("Server not found")

        # Update server fields
        for field, value in server_data.dict(exclude_unset=True).items():
            if field == "credentials":
                continue  # Handle credentials separately
            setattr(server, field, value)

        # Update credentials if provided
        if server_data.credentials:
            # Remove existing credentials
            existing_credential = self.db.query(Credential).filter(
                Credential.server_id == server_id
            ).first()
            if existing_credential:
                self.db.delete(existing_credential)

            # Add new credentials
            encrypted_credentials = credential_encryption.encrypt_credentials(server_data.credentials)
            new_credential = Credential(
                server_id=server.id,
                encrypted_payload=encrypted_credentials,
                auth_type="api_key"
            )
            self.db.add(new_credential)

        self.db.commit()
        self.db.refresh(server)
        return server

    def delete_server(self, server_id: int):
        server = self.get_server_by_id(server_id)
        if not server:
            raise ValueError("Server not found")

        # Delete associated credentials (cascading should handle this)
        self.db.delete(server)
        self.db.commit()