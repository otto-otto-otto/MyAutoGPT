"""
一次性脚本：为所有未收到初始积分的老用户补发 500 credits。

运行方式（在 backend 目录下）：
    python retroactive_credits.py

因为使用 transaction_key="INITIAL_GRANT-{user_id}" 保证幂等，
即使重复运行也不会重复发放。
"""

import asyncio
import logging
import sys
from pathlib import Path

# 确保 backend 包在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent))

from prisma import Prisma
from prisma.enums import CreditTransactionType
from backend.data.credit import UserCredit
from backend.util.json import SafeJson

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("retroactive_credits")

INITIAL_GRANT_AMOUNT = 500
INITIAL_GRANT_REASON = "Initial sign-up grant (retroactive)"


async def main():
    prisma = Prisma()
    await prisma.connect()

    try:
        # 1. 查出所有用户
        all_users = await prisma.user.find_many()
        logger.info(f"Found {len(all_users)} total users")

        # 2. 查出已发放过 INITIAL_GRANT 的用户（通过 CreditTransaction 表）
        existing_grants = await prisma.credittransaction.find_many(
            where={
                "transactionType": CreditTransactionType.GRANT,
                "OR": [
                    {"transactionKey": {"startswith": "INITIAL_GRANT-"}},
                    {"transactionKey": {"startswith": "initial-grant-"}},
                ],
            }
        )
        already_granted_ids = {txn.userId for txn in existing_grants}
        logger.info(f"Already granted: {len(already_granted_ids)} users")

        # 3. 找出需要补发的用户
        users_to_grant = [
            u for u in all_users if u.id not in already_granted_ids
        ]
        logger.info(f"Users needing retroactive grant: {len(users_to_grant)}")

        if not users_to_grant:
            logger.info("All users already have initial credits, nothing to do.")
            return

        # 4. 逐个发放
        credit = UserCredit()
        success = 0
        failed = 0

        for user in users_to_grant:
            tx_key = f"INITIAL_GRANT-{user.id}"
            try:
                new_balance, result_key = await credit._add_transaction(
                    user_id=user.id,
                    amount=INITIAL_GRANT_AMOUNT,
                    transaction_type=CreditTransactionType.GRANT,
                    transaction_key=tx_key,
                    metadata=SafeJson(
                        {"reason": INITIAL_GRANT_REASON, "source": "retroactive_script"}
                    ),
                )
                logger.info(
                    f"  ✓ Granted {INITIAL_GRANT_AMOUNT} to {user.email or user.id} "
                    f"(balance={new_balance}, key={result_key})"
                )
                success += 1
            except Exception as e:
                logger.error(f"  ✗ Failed for {user.email or user.id}: {e}")
                failed += 1

        logger.info(f"Done. Success={success}, Failed={failed}")

    finally:
        await prisma.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
