"""
Database models and operations for LIMS data storage
"""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.dialects.postgresql import insert
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
    
    __table_args__ = (
        UniqueConstraint('folio_grd', 'cliente_grd', 'fecha_recep', name='sample_unique_constraint'),
    )


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
        """Save sample data to database using upsert to handle duplicates"""
        session = self.get_session()
        try:
            saved_count = 0
            
            if self.engine.dialect.name == 'postgresql':
                # Use PostgreSQL UPSERT for better performance
                saved_count = self._upsert_postgresql(session, samples_data)
            else:
                # Use standard approach for other databases
                saved_count = self._upsert_standard(session, samples_data)
            
            session.commit()
            return saved_count
        finally:
            session.close()
    
    def _upsert_postgresql(self, session, samples_data: List[Dict[str, Any]]) -> int:
        """PostgreSQL-specific upsert using ON CONFLICT"""
        saved_count = 0
        for sample_data in samples_data:
            stmt = insert(Sample).values(
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
            # Update on conflict with latest data
            stmt = stmt.on_conflict_do_update(
                constraint='sample_unique_constraint',
                set_=dict(
                    fecha_grd=stmt.excluded.fecha_grd,
                    fec_cap_res=stmt.excluded.fec_cap_res,
                    fec_libera=stmt.excluded.fec_libera,
                    suc_proc=stmt.excluded.suc_proc,
                    maquilador=stmt.excluded.maquilador,
                    label1=stmt.excluded.label1,
                    label3=stmt.excluded.label3
                )
            )
            session.execute(stmt)
            saved_count += 1
        return saved_count
    
    def _upsert_standard(self, session, samples_data: List[Dict[str, Any]]) -> int:
        """Standard upsert for SQLite and other databases"""
        saved_count = 0
        for sample_data in samples_data:
            # Check if record exists
            existing = session.query(Sample).filter_by(
                folio_grd=sample_data.get('_lblFolioGrd'),
                cliente_grd=sample_data.get('_lblClienteGrd'),
                fecha_recep=sample_data.get('_lblFechaRecep')
            ).first()
            
            if existing:
                # Update existing record
                existing.fecha_grd = sample_data.get('_lblFechaGrd')
                existing.fec_cap_res = sample_data.get('_lblFecCapRes')
                existing.fec_libera = sample_data.get('_lblFecLibera')
                existing.suc_proc = sample_data.get('_lblSucProc')
                existing.maquilador = sample_data.get('_lblMaquilador')
                existing.label1 = sample_data.get('_Label1')
                existing.label3 = sample_data.get('_Label3')
            else:
                # Insert new record
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
        return saved_count
    
    def get_sample_count(self) -> int:
        """Get total number of samples in database"""
        session = self.get_session()
        try:
            return session.query(Sample).count()
        finally:
            session.close()