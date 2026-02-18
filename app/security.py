import bcrypt

def verify_password(plain_password: str, hashed_password: str):
    return bcrypt.checkpw(
        plain_password.encode('utf-8'), 
        hashed_password.encode('utf-8') if isinstance(hashed_password, str) else hashed_password
    )

def get_password_hash(password: str):
    # Hash a password for the first time
    # (with a randomly-generated salt)
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

