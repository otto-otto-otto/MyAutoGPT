"""
Admin routes for user management — list all users with credit summaries.
"""

import logging
from typing import Any

from autogpt_libs.auth import get_user_id, requires_super_admin
from fastapi import APIRouter, HTTPException, Query, Security

from backend.data.db import query_raw_with_schema
from backend.util.models import Pagination

from .model import AdminUserSummary, AdminUsersListResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin",
    tags=["users", "admin"],
    dependencies=[Security(requires_super_admin)],
)


@router.get(
    "/users",
    response_model=AdminUsersListResponse,
    summary="List All Users with Credit Summaries",
)
async def admin_list_all_users(
    admin_user_id: str = Security(get_user_id),
    search: str | None = Query(
        None, description="Search users by email or name (case-insensitive)"
    ),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Users per page"),
) -> AdminUsersListResponse:
    """List all users with their current credit balance and total consumption.

    Supports pagination and optional search filtering by email or name.
    Only accessible by super admins (admin role + whitelist match).
    """
    logger.info(
        "Super admin %s listing all users (page=%s, size=%s, search=%s)",
        admin_user_id,
        page,
        page_size,
        search,
    )

    try:
        # Build WHERE clause for search
        where_clause = ""
        params: dict[str, Any] = {}

        if search and search.strip():
            search_term = f"%{search.strip()}%"
            params["search"] = search_term
            where_clause = """
                WHERE u.email ILIKE :search OR u.name ILIKE :search
            """

        # Count total users
        count_sql = f"""
            SELECT COUNT(*) AS total
            FROM "User" u
            {where_clause}
        """
        count_result = await query_raw_with_schema(count_sql, params, {})
        total = count_result[0]["total"] if count_result else 0

        total_pages = max(1, (total + page_size - 1) // page_size) if total > 0 else 0

        # Fetch users with balance and consumption
        # Uses LEFT JOIN so users without balance/transactions still appear
        params["limit"] = page_size
        params["offset"] = (page - 1) * page_size

        list_sql = f"""
            SELECT
                u.id AS user_id,
                u.email AS email,
                u.name AS name,
                COALESCE(ub.balance, 0) AS balance,
                COALESCE(SUM(
                    CASE WHEN ct.type = 'USAGE' AND ct."isActive" = true
                    THEN ABS(ct.amount)
                    ELSE 0
                    END
                ), 0) AS total_consumption,
                u."createdAt" AS created_at
            FROM "User" u
            LEFT JOIN "UserBalance" ub ON ub."userId" = u.id
            LEFT JOIN "CreditTransaction" ct ON ct."userId" = u.id
            {where_clause}
            GROUP BY u.id, u.email, u.name, ub.balance, u."createdAt"
            ORDER BY u."createdAt" DESC
            LIMIT :limit OFFSET :offset
        """

        rows = await query_raw_with_schema(list_sql, params, {})

        users = [
            AdminUserSummary(
                user_id=row["user_id"],
                email=row["email"],
                name=row["name"],
                balance=row["balance"],
                total_consumption=row["total_consumption"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

        pagination = Pagination(
            total_items=total,
            total_pages=total_pages,
            current_page=page,
            page_size=page_size,
        )

        logger.info(
            "Super admin %s retrieved %d users (page %d/%d)",
            admin_user_id,
            len(users),
            page,
            total_pages,
        )

        return AdminUsersListResponse(users=users, pagination=pagination)

    except Exception as e:
        logger.exception("Error listing users for super admin %s: %s", admin_user_id, e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve user list: {e}",
        ) from e
