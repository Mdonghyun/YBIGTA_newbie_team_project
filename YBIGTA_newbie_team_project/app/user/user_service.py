from app.user.user_repository import UserRepository
from app.user.user_schema import User, UserLogin, UserUpdate

class UserService:
    def __init__(self, userRepoitory: UserRepository) -> None:
        self.repo = userRepoitory

    def login(self, user_login: UserLogin) -> User:
        ## TODO
        """
        Authenticate a user by email and password.

        Raises:
            ValueError("User not Found.") if 이메일이 존재하지 않을 때
            ValueError("Invalid ID/PW") if 비밀번호 불일치 시
        Returns:
            User: 로그인에 성공한 사용자 정보
        """
        existing = self.repo.get_user_by_email(user_login.email)
        if existing is None:
            raise ValueError("User not Found.")
        if existing.password != user_login.password:
            raise ValueError("Invalid ID/PW")
        return existing
        
    def register_user(self, new_user: User) -> User:
        ## TODO
        """
        Register a new user.

        Raises:
            ValueError("User already Exists.") if 이메일 중복 시
        Returns:
            User: 생성된 사용자 정보
        """
        if self.repo.get_user_by_email(new_user.email) is not None:
            raise ValueError("User already Exists.")
        user = self.repo.save_user(new_user)
        return user


    def delete_user(self, email: str) -> User:
        ## TODO        
        """
        Delete an existing user by email.

        Raises:
            ValueError("User not Found.") if 이메일이 존재하지 않을 때
        Returns:
            User: 삭제된 사용자 정보
        """
        existing = self.repo.get_user_by_email(email)
        if existing is None:
            raise ValueError("User not Found.")
        deleted = self.repo.delete_user(existing)
        return deleted

    def update_user_pwd(self, user_update: UserUpdate) -> User:
        """
        Update a user's password.

        Raises:
            ValueError("User not Found.") if 이메일이 존재하지 않을 때
        Returns:
            User: 비밀번호가 업데이트된 사용자 정보
        """
        existing = self.repo.get_user_by_email(user_update.email)
        if existing is None:
            raise ValueError("User not Found.")
        existing.password = user_update.new_password
        updated = self.repo.save_user(existing)
        return updated
        