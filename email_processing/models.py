from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class WebhookProcessingRecord(Base):
    __tablename__ = 'webhook_processing_record'
    
    id = Column(Integer, primary_key=True, index=True)
    webhook_id = Column(String, unique=True, index=True)
    processed_successfully = Column(Boolean, default=False)
    last_processed_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<WebhookProcessingRecord {self.id}>'
