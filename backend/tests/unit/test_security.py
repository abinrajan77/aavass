from app.services.security import hash_password, verify_password


def test_hash_password_produces_argon2id_hash():
    hashed = hash_password("correct horse battery staple")
    assert hashed.startswith("$argon2id$")


def test_verify_password_succeeds_for_correct_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_password_fails_for_incorrect_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_hash_never_matches_plaintext_via_string_equality():
    """Regression guard against ever regressing to plaintext/naive hashing."""
    plaintext = "correct horse battery staple"
    hashed = hash_password(plaintext)
    assert hashed != plaintext
    assert plaintext not in hashed


def test_same_password_produces_different_hashes_due_to_salting():
    h1 = hash_password("same-password")
    h2 = hash_password("same-password")
    assert h1 != h2
    assert verify_password("same-password", h1)
    assert verify_password("same-password", h2)


def test_verify_password_rejects_malformed_hash_without_raising():
    assert verify_password("anything", "not-a-real-hash") is False
