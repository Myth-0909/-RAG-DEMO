from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.user import User
from app.models.knowledge import Domain
from app.schemas.knowledge import DomainCreate, DomainUpdate, DomainResponse
from app.core.deps import get_current_user, get_current_superuser

router = APIRouter(prefix="/domains", tags=["专业领域"])


@router.get("/", response_model=List[DomainResponse])
def list_domains(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return db.query(Domain).all()


@router.post("/", response_model=DomainResponse)
def create_domain(
    domain_in: DomainCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_superuser),
):
    domain = Domain(**domain_in.model_dump())
    db.add(domain)
    db.commit()
    db.refresh(domain)
    return domain


@router.get("/{domain_id}", response_model=DomainResponse)
def get_domain(
    domain_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="领域不存在")
    return domain


@router.put("/{domain_id}", response_model=DomainResponse)
def update_domain(
    domain_id: int,
    domain_in: DomainUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_superuser),
):
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="领域不存在")

    for key, value in domain_in.model_dump(exclude_unset=True).items():
        setattr(domain, key, value)

    db.commit()
    db.refresh(domain)
    return domain


@router.delete("/{domain_id}")
def delete_domain(
    domain_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_superuser),
):
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="领域不存在")
    db.delete(domain)
    db.commit()
    return {"detail": "删除成功"}
