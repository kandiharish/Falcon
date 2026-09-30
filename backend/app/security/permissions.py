"""Role-based access control (plan §3, §26).

Roles are fixed job functions; permissions are the actions the API checks.
The mapping lives in code so every change is reviewed and versioned in Git.
Least privilege: the system administrator manages users and settings but
cannot read evidence — administering the system is not investigating.
"""

from enum import StrEnum


class Role(StrEnum):
    INVESTIGATION_OFFICER = "investigation_officer"
    FORENSIC_ANALYST = "forensic_analyst"
    EVIDENCE_ANALYST = "evidence_analyst"
    INCIDENT_INVESTIGATOR = "incident_investigator"
    SUPERVISOR = "supervisor"
    SYSTEM_ADMIN = "system_admin"


class Permission(StrEnum):
    INVESTIGATION_READ = "investigation:read"
    INVESTIGATION_WRITE = "investigation:write"
    EVIDENCE_READ = "evidence:read"
    EVIDENCE_UPLOAD = "evidence:upload"
    EVIDENCE_VERIFY = "evidence:verify"
    CORRELATION_REVIEW = "correlation:review"
    REPORT_GENERATE = "report:generate"
    TASK_MANAGE = "task:manage"
    AUDIT_READ = "audit:read"
    USERS_READ = "users:read"
    USERS_MANAGE = "users:manage"
    SETTINGS_MANAGE = "settings:manage"


P = Permission

_INVESTIGATOR = {
    P.INVESTIGATION_READ,
    P.INVESTIGATION_WRITE,
    P.EVIDENCE_READ,
    P.EVIDENCE_UPLOAD,
    P.CORRELATION_REVIEW,
    P.REPORT_GENERATE,
    P.TASK_MANAGE,
}

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.INVESTIGATION_OFFICER: frozenset(_INVESTIGATOR),
    Role.INCIDENT_INVESTIGATOR: frozenset(_INVESTIGATOR),
    Role.FORENSIC_ANALYST: frozenset(
        {
            P.INVESTIGATION_READ,
            P.EVIDENCE_READ,
            P.EVIDENCE_UPLOAD,
            P.EVIDENCE_VERIFY,
            P.CORRELATION_REVIEW,
            P.TASK_MANAGE,
        }
    ),
    Role.EVIDENCE_ANALYST: frozenset(
        {P.INVESTIGATION_READ, P.EVIDENCE_READ, P.EVIDENCE_UPLOAD, P.TASK_MANAGE}
    ),
    Role.SUPERVISOR: frozenset(
        {
            P.INVESTIGATION_READ,
            P.INVESTIGATION_WRITE,
            P.EVIDENCE_READ,
            P.EVIDENCE_VERIFY,
            P.CORRELATION_REVIEW,
            P.REPORT_GENERATE,
            P.TASK_MANAGE,
            P.AUDIT_READ,
            P.USERS_READ,
        }
    ),
    Role.SYSTEM_ADMIN: frozenset({P.USERS_READ, P.USERS_MANAGE, P.SETTINGS_MANAGE, P.AUDIT_READ}),
}


def permissions_for(role: str) -> frozenset[Permission]:
    """Unknown roles get no permissions (fail closed)."""
    try:
        return ROLE_PERMISSIONS[Role(role)]
    except ValueError:
        return frozenset()
