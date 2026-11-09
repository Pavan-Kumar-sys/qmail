import os
import base64
import hashlib
import secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Quantum-Safe Lattice Parameters (Learning With Errors / Kyber-style KEM)
N = 64        # Lattice dimension
Q = 3329      # Official Kyber prime modulus

def _bytes_to_numbers(data: bytes):
    return [int.from_bytes(data[i:i+2], 'big') % Q for i in range(0, len(data), 2)]

def _numbers_to_bytes(nums):
    return b''.join((x % Q).to_bytes(2, 'big') for x in nums)

def generate_quantum_keys():
    """Creates a Quantum-Safe Public Lock and Private Key using Lattice LWE math."""
    seed = os.urandom(32)
    # Secret key: small secret numbers (-1, 0, or 1)
    s = [secrets.randbelow(3) - 1 for _ in range(N)]
    
    # Build public puzzle using the seed and small random noise
    b = []
    for i in range(N):
        row_hash = hashlib.shake_128(seed + i.to_bytes(2, 'big')).digest(N * 2)
        row = _bytes_to_numbers(row_hash)
        noise = secrets.randbelow(3) - 1
        val = (sum(row[j] * s[j] for j in range(N)) + noise) % Q
        b.append(val)
        
    pub_bytes = seed + _numbers_to_bytes(b)
    sec_bytes = _numbers_to_bytes(s)
    return {
        "public_key": base64.b64encode(pub_bytes).decode('utf-8'),
        "secret_key": base64.b64encode(sec_bytes).decode('utf-8')
    }

def encrypt_email(public_key_b64: str, message_text: str):
    """Locks the email inside a Quantum Lattice Capsule + AES-256-GCM."""
    pub_bytes = base64.b64decode(public_key_b64)
    seed = pub_bytes[:32]
    b = _bytes_to_numbers(pub_bytes[32:])
    
    # 1. Create a random 32-byte secret key (256 bits) to lock the email
    raw_secret = os.urandom(32)
    bits = [(raw_secret[i // 8] >> (i % 8)) & 1 for i in range(256)]
    
    # 2. Wrap each bit inside a Quantum Lattice puzzle
    capsule_nums = []
    for bit in bits:
        r = [secrets.randbelow(3) - 1 for _ in range(N)]
        u = []
        for j in range(N):
            col_sum = 0
            for i in range(N):
                row_hash = hashlib.shake_128(seed + i.to_bytes(2, 'big')).digest(N * 2)
                row = _bytes_to_numbers(row_hash)
                col_sum += row[j] * r[i]
            u.append(col_sum % Q)
        v = (sum(b[i] * r[i] for i in range(N)) + bit * (Q // 2)) % Q
        capsule_nums.extend(u + [v])
        
    shared_secret = hashlib.sha256(raw_secret).digest()
    
    # 3. Scramble the email text with AES-256-GCM
    aesgcm = AESGCM(shared_secret)
    nonce = os.urandom(12)
    encrypted_message = aesgcm.encrypt(nonce, message_text.encode('utf-8'), None)
    
    return {
        "kem_capsule": base64.b64encode(_numbers_to_bytes(capsule_nums)).decode('utf-8'),
        "nonce": base64.b64encode(nonce).decode('utf-8'),
        "ciphertext": base64.b64encode(encrypted_message).decode('utf-8')
    }

def decrypt_email(secret_key_b64: str, kem_capsule_b64: str, nonce_b64: str, ciphertext_b64: str):
    """Unlocks the Quantum Lattice Capsule with the Private Key and reads the email."""
    sec_nums = _bytes_to_numbers(base64.b64decode(secret_key_b64))
    s = [x - Q if x > Q // 2 else x for x in sec_nums]
    
    capsule_nums = _bytes_to_numbers(base64.b64decode(kem_capsule_b64))
    nonce = base64.b64decode(nonce_b64)
    ciphertext = base64.b64decode(ciphertext_b64)
    
    # 1. Solve the lattice puzzle using the secret key to get the 256 bits back
    bits = []
    step = N + 1
    for idx in range(256):
        chunk = capsule_nums[idx * step : (idx + 1) * step]
        u, v = chunk[:N], chunk[N]
        diff = (v - sum(u[j] * s[j] for j in range(N))) % Q
        bit = 1 if (Q // 4 < diff < 3 * Q // 4) else 0
        bits.append(bit)
        
    raw_secret = bytes(
        sum(bits[i * 8 + k] << k for k in range(8)) for i in range(32)
    )
    shared_secret = hashlib.sha256(raw_secret).digest()
    
    # 2. Unlock the scrambled email text
    aesgcm = AESGCM(shared_secret)
    decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return decrypted_bytes.decode('utf-8')

# Quick test when we run this file directly
if __name__ == "__main__":
    print("1. Generating Quantum Lattice Keys (LWE-Kyber Engine)...")
    keys = generate_quantum_keys()
    print("   Public Key Sample:", keys["public_key"][:40] + "...")
    
    secret_msg = "Hello! This email is protected against quantum computers."
    print("\n2. Locking message:", secret_msg)
    locked = encrypt_email(keys["public_key"], secret_msg)
    print("   Scrambled Text:", locked["ciphertext"][:40] + "...")
    
    print("\n3. Unlocking message with Private Key...")
    unlocked = decrypt_email(keys["secret_key"], locked["kem_capsule"], locked["nonce"], locked["ciphertext"])
    print("   Unlocked Message:", unlocked)