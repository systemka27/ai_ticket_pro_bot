from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, BigInteger, Index, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()

class ChatStatus(enum.Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    TRANSFERRED = "transferred"  # Добавил статус для переданных оператору чатов
    PENDING = "pending"

class Client(Base):
    __tablename__ = 'clients'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    language_code = Column(String(10))
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)  # Добавил для отслеживания активности
    
    # Связи
    chats = relationship("Chat", back_populates="client")
    
    # Индексы для производительности
    __table_args__ = (
        Index('ix_clients_telegram_id', 'telegram_id'),
        Index('ix_clients_username', 'username'),
        Index('ix_clients_last_activity', 'last_activity'),  # Добавил индекс для активности
    )

class Chat(Base):
    __tablename__ = 'chats'
    
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False, index=True)
    status = Column(Enum(ChatStatus), default=ChatStatus.ACTIVE)  # Используем Enum
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    transferred_at = Column(DateTime, nullable=True)  # Время передачи оператору
    operator_id = Column(Integer, nullable=True)  # ID оператора, если чат передан
    
    # Связи
    client = relationship("Client", back_populates="chats")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")
    
    # Индексы
    __table_args__ = (
        Index('ix_chats_client_id', 'client_id'),
        Index('ix_chats_status', 'status'),
        Index('ix_chats_updated_at', 'updated_at'),
    )

class Message(Base):
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey('chats.id'), nullable=False, index=True)
    text = Column(Text)
    is_from_user = Column(Boolean, default=True)
    message_type = Column(String(20), default='text')  # text, system, operator_transfer
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    chat = relationship("Chat", back_populates="messages")
    
    # Индексы
    __table_args__ = (
        Index('ix_messages_chat_id', 'chat_id'),
        Index('ix_messages_created_at', 'created_at'),
        Index('ix_messages_is_from_user', 'is_from_user'),
    )