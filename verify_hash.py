from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

password = "password123"
# Replace with the actual hash from DB for testuser@example.com
# I'll need to get the full hash first.
hash_from_db = "$pbkdf2-sha256$29000$a22NZRbrZJg9RirHWuvf.fw$0wyPDrsGaUkJK7CHelnoTxsP.mdN6PNMM8gcZ" # I'll get this in next step

def verify(p, h):
    try:
        res = pwd_context.verify(p, h)
        print(f"Verification result: {res}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        verify(password, sys.argv[1])
    else:
        print("Please provide the hash as an argument")
