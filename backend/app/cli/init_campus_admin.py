import argparse

from app.core.config import get_security_settings
from app.core.database import get_session_factory
from app.core.security import SecurityService
from app.repositories.campus import CampusRepository
from app.services.campus import CampusService


def main() -> None:
    parser = argparse.ArgumentParser(
        description="将明确指定的现有账号初始化为首个校园管理员"
    )
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--reason", required=True)
    arguments = parser.parse_args()
    if arguments.user_id <= 0 or len(arguments.reason.strip()) < 3:
        parser.error("user-id 必须为正整数，reason 至少 3 个字符")

    session = get_session_factory()()
    try:
        service = CampusService(
            CampusRepository(session), SecurityService(get_security_settings())
        )
        membership = service.initialize_first_admin(
            user_id=arguments.user_id, reason=arguments.reason.strip()
        )
        print(f"已初始化校园管理员，membership_id={membership.id}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
