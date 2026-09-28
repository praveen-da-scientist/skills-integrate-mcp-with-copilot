import getpass
import json

from app import hash_password, teacher_credentials_file


def main():
    username = input("Teacher username: ").strip()
    if not username:
        raise SystemExit("Username cannot be empty")

    password = getpass.getpass("Teacher password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if not password:
        raise SystemExit("Password cannot be empty")
    if password != confirmation:
        raise SystemExit("Passwords do not match")

    credentials = {}
    if teacher_credentials_file.exists():
        try:
            credentials = json.loads(
                teacher_credentials_file.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as error:
            raise SystemExit(f"Cannot read teacher credentials: {error}") from error
        if not isinstance(credentials, dict) or any(
            not isinstance(name, str) or not isinstance(password_hash, str)
            for name, password_hash in credentials.items()
        ):
            raise SystemExit("Teacher credentials must map usernames to password hashes")

    if username in credentials:
        replace = input("Username exists. Replace its password? [y/N]: ").strip().lower()
        if replace != "y":
            raise SystemExit("No changes made")

    credentials[username] = hash_password(password)
    teacher_credentials_file.parent.mkdir(parents=True, exist_ok=True)
    teacher_credentials_file.write_text(
        json.dumps(credentials, indent=2) + "\n", encoding="utf-8"
    )
    teacher_credentials_file.chmod(0o600)
    print(f"Teacher account saved to {teacher_credentials_file}")


if __name__ == "__main__":
    main()