"""
Database models and operations for LIMS data storage
"""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone
import os
from typing import List, Dict, Any

Base = declarative_base()


class Sample(Base):
    __tablename__ = 'samples'
    
    id = Column(Integer, primary_key=True)
    fecha_grd = Column(DateTime)
    fecha_recep = Column(DateTime)
    folio_grd = Column(Integer)
    cliente_grd = Column(Integer)
    paciente_grd = Column(Integer)
    est_per_grd = Column(Integer)
    label1 = Column(String(255))
    fec_cap_res = Column(DateTime)
    fec_libera = Column(DateTime)
    suc_proc = Column(String(255))
    maquilador = Column(String(255))
    label3 = Column(String(255))
    fec_nac = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class DatabaseManager:
    """Handles database connections and operations"""
    
    def __init__(self, connection_string: str = None):
        if not connection_string:
            connection_string = self._get_connection_string()
        
        self.engine = create_engine(connection_string)
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def _get_connection_string(self) -> str:
        """Build connection string from environment variables"""
        host = os.getenv('DB_HOST', 'localhost')
        port = os.getenv('DB_PORT', '5432')
        name = os.getenv('DB_NAME', 'lims_etl')
        user = os.getenv('DB_USER', 'postgres')
        password = os.getenv('DB_PASSWORD', 'postgres')
        
        return f"postgresql://{user}:{password}@{host}:{port}/{name}"
    
    def create_tables(self):
        """Create database tables"""
        Base.metadata.create_all(self.engine)
    
    def get_session(self):
        """Get database session"""
        return self.SessionLocal()
    
    def save_samples(self, samples_data: List[Dict[str, Any]]) -> int:
        """Save sample data to database"""
        session = self.get_session()
        try:
            saved_count = 0
            for sample_data in samples_data:
                sample = Sample(
                    fecha_grd=sample_data.get('_lblFechaGrd'),
                    fecha_recep=sample_data.get('_lblFechaRecep'),
                    folio_grd=sample_data.get('_lblFolioGrd'),
                    cliente_grd=sample_data.get('_lblClienteGrd'),
                    paciente_grd=sample_data.get('_lblPacienteGrd'),
                    est_per_grd=sample_data.get('_lblEstPerGrd'),
                    label1=sample_data.get('_Label1'),
                    fec_cap_res=sample_data.get('_lblFecCapRes'),
                    fec_libera=sample_data.get('_lblFecLibera'),
                    suc_proc=sample_data.get('_lblSucProc'),
                    maquilador=sample_data.get('_lblMaquilador'),
                    label3=sample_data.get('_Label3'),
                    fec_nac=sample_data.get('_lblFecNac')
                )
                session.add(sample)
                saved_count += 1
            
            session.commit()
            return saved_count
        finally:
            session.close()
    
    def get_sample_count(self) -> int:
        """Get total number of samples in database"""
        session = self.get_session()
        try:
            return session.query(Sample).count()
        finally:
            session.close()