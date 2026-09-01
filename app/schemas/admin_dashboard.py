from pydantic import BaseModel


class AdminUserStats(BaseModel):
    total: int
    candidates: int
    recruiters: int
    admins: int
    active: int
    inactive: int


class AdminJobStats(BaseModel):
    total: int
    pending: int
    approved: int
    rejected: int
    closed: int


class AdminApplicationStats(BaseModel):
    total: int
    submitted: int
    reviewing: int
    shortlisted: int
    rejected: int
    hired: int
    withdrawn: int


class AdminCVStats(BaseModel):
    total: int


class AdminCVTemplateStats(BaseModel):
    total: int
    active: int
    inactive: int


class AdminDashboardResponse(BaseModel):
    users: AdminUserStats
    jobs: AdminJobStats
    applications: AdminApplicationStats
    cvs: AdminCVStats
    cv_templates: AdminCVTemplateStats
