from dataclasses import dataclass
from typing import Optional, Protocol

from sqlalchemy.orm import Session

from shared.db.models import Department, User


@dataclass
class DepartmentInfo:
    name: str
    max_users: int
    current_users: int
    license_type: str


@dataclass
class ProvisionResult:
    success: bool
    license_type: Optional[str] = None
    available_licenses: Optional[int] = None
    reason: Optional[str] = None
    requires_approval: bool = False


@dataclass
class SiteStatus:
    total_departments: int
    total_active_users: int
    total_capacity: int


class TableauBackend(Protocol):
    """Everything an agent needs from the Tableau site.

    `SimulatedTableauBackend` (below) is the only implementation today. A future
    `TableauCloudBackend` talking to the real Tableau REST API can implement the
    same interface without any agent code changing.
    """

    def get_department(self, name: str) -> Optional[DepartmentInfo]: ...
    def check_capacity(self, department: str, requested_users: int) -> ProvisionResult: ...
    def provision_user(self, email: str, department: str) -> bool: ...
    def deactivate_user(self, email: str) -> bool: ...
    def get_site_status(self) -> SiteStatus: ...


class SimulatedTableauBackend:
    def __init__(self, db: Session):
        self.db = db

    def get_department(self, name: str) -> Optional[DepartmentInfo]:
        dept = self.db.query(Department).filter(Department.name == name).first()
        if dept is None:
            return None
        current_users = (
            self.db.query(User)
            .filter(User.department_id == dept.id, User.status == "active")
            .count()
        )
        return DepartmentInfo(
            name=dept.name,
            max_users=dept.max_users,
            current_users=current_users,
            license_type=dept.license.name,
        )

    def check_capacity(self, department: str, requested_users: int) -> ProvisionResult:
        dept_info = self.get_department(department)
        if dept_info is None:
            return ProvisionResult(success=False, reason="Department not found")

        available = dept_info.max_users - dept_info.current_users
        if requested_users <= available:
            return ProvisionResult(
                success=True,
                license_type=dept_info.license_type,
                available_licenses=available,
            )
        return ProvisionResult(
            success=False,
            reason=f"Insufficient licenses. Requested: {requested_users}, Available: {available}",
            requires_approval=True,
        )

    def provision_user(self, email: str, department: str) -> bool:
        dept = self.db.query(Department).filter(Department.name == department).first()
        if dept is None:
            return False

        user = self.db.query(User).filter(User.email == email).first()
        if user is not None:
            user.status = "active"
            user.department_id = dept.id
            user.license_id = dept.license_id
        else:
            self.db.add(User(email=email, department_id=dept.id, license_id=dept.license_id))
        self.db.commit()
        return True

    def deactivate_user(self, email: str) -> bool:
        user = self.db.query(User).filter(User.email == email, User.status == "active").first()
        if user is None:
            return False
        user.status = "removed"
        self.db.commit()
        return True

    def get_site_status(self) -> SiteStatus:
        departments = self.db.query(Department).all()
        total_active_users = self.db.query(User).filter(User.status == "active").count()
        return SiteStatus(
            total_departments=len(departments),
            total_active_users=total_active_users,
            total_capacity=sum(d.max_users for d in departments),
        )
