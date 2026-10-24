"""
main.py
=======

Example usage of the A5-GMR-1 reference implementation.

Run directly with:

    cd a5_gmr1
    python3 main.py
"""

from cipher import A5GMR1


def main() -> None:
    key = bytes([0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF])
    frame_number = 42

    # --- Basic keystream generation -------------------------------------
    cipher = A5GMR1(key=key, frame_number=frame_number)
    cipher.initialize()
    keystream = cipher.generate_keystream(114)
    print("First 114 keystream bits:")
    print("".join(str(bit) for bit in keystream))
    print()

    # --- Encrypt / decrypt round trip -----------------------------------
    plaintext = [1, 0, 1, 1, 0, 0, 1, 0] * 14  # 112 bits of sample data

    encrypt_cipher = A5GMR1(key=key, frame_number=frame_number)
    encrypt_cipher.initialize()
    ciphertext = encrypt_cipher.encrypt(plaintext)

    decrypt_cipher = A5GMR1(key=key, frame_number=frame_number)
    decrypt_cipher.initialize()
    recovered = decrypt_cipher.decrypt(ciphertext)

    print("Plaintext :", "".join(str(b) for b in plaintext))
    print("Ciphertext:", "".join(str(b) for b in ciphertext))
    print("Recovered :", "".join(str(b) for b in recovered))
    print("Round trip successful:", recovered == plaintext)
    print()

    # --- Debug trace mode -------------------------------------------------
    print("Debug trace of the first 3 rounds after initialization:")
    traced_cipher = A5GMR1(key=key, frame_number=frame_number, trace=True)
    traced_cipher.initialize()
    traced_cipher.generate_keystream(3)


if __name__ == "__main__":
    main()
