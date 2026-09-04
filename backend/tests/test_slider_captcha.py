from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import Mock

from app.api.deps import get_auth_service
from app.core.exceptions import AuthenticationRequiredError
from app.core.security import AccessToken
from app.main import create_app
from app.services.slider_captcha import (
    SliderCaptchaBusyError,
    SliderCaptchaError,
    SliderCaptchaService,
    get_slider_captcha_service,
)
from tests.test_api_foundation import request


class SliderCaptchaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = 100.0
        self.captcha = SliderCaptchaService(clock=lambda: self.now)

    def verified_token(self) -> str:
        challenge = self.captcha.create_challenge()
        self.now += 0.6
        return self.captcha.verify(challenge.value, 100).value

    def test_challenge_cannot_be_used_as_login_token(self) -> None:
        challenge = self.captcha.create_challenge()
        with self.assertRaises(SliderCaptchaError):
            self.captcha.consume(challenge.value)

    def test_token_is_one_time_even_with_concurrent_consumers(self) -> None:
        token = self.verified_token()

        def consume(_: int) -> bool:
            try:
                self.captcha.consume(token)
                return True
            except SliderCaptchaError:
                return False

        with ThreadPoolExecutor(max_workers=4) as executor:
            self.assertEqual(sum(executor.map(consume, range(4))), 1)

    def test_partial_drag_consumes_challenge(self) -> None:
        challenge = self.captcha.create_challenge()
        self.now += 1
        for position in (70, 100):
            with self.assertRaises(SliderCaptchaError):
                self.captcha.verify(challenge.value, position)

    def test_instant_submission_and_expired_challenge_are_rejected(self) -> None:
        challenge = self.captcha.create_challenge()
        with self.assertRaises(SliderCaptchaError):
            self.captcha.verify(challenge.value, 100)
        challenge = self.captcha.create_challenge()
        self.now += self.captcha.challenge_ttl
        with self.assertRaises(SliderCaptchaError):
            self.captcha.verify(challenge.value, 100)

    def test_verified_token_expires(self) -> None:
        token = self.verified_token()
        self.now += self.captcha.token_ttl
        with self.assertRaises(SliderCaptchaError):
            self.captcha.consume(token)

    def test_capacity_recovers_after_expiration(self) -> None:
        captcha = SliderCaptchaService(clock=lambda: self.now, capacity=1)
        captcha.create_challenge()
        with self.assertRaises(SliderCaptchaBusyError):
            captcha.create_challenge()
        self.now += captcha.challenge_ttl
        self.assertIsNotNone(captcha.create_challenge())


class SliderCaptchaAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = 100.0
        self.captcha = SliderCaptchaService(clock=lambda: self.now)
        self.auth = Mock()
        self.auth.login.return_value = AccessToken(value="test-access-token", expires_in=1800)
        self.app = create_app()
        self.app.dependency_overrides[get_auth_service] = lambda: self.auth
        self.app.dependency_overrides[get_slider_captcha_service] = lambda: self.captcha

    def token(self) -> str:
        challenge = request(self.app, "POST", "/api/v1/auth/slider/challenge")
        self.assertEqual(challenge.status_code, 200)
        self.assertEqual(challenge.headers["cache-control"], "no-store")
        self.now += 0.6
        verified = request(self.app, "POST", "/api/v1/auth/slider/verify", body={
            "challenge_id": challenge.json()["challenge_id"], "position": 100,
        })
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(verified.headers["cache-control"], "no-store")
        return verified.json()["slider_token"]

    def test_login_requires_verified_token_and_rejects_replay(self) -> None:
        body = {"identifier": "student_01", "password": "correct-password"}
        missing = request(self.app, "POST", "/api/v1/auth/login", body=body)
        self.assertEqual(missing.status_code, 422)
        self.auth.login.assert_not_called()
        body["slider_token"] = "x" * 43
        invalid = request(self.app, "POST", "/api/v1/auth/login", body=body)
        self.assertEqual(invalid.status_code, 400)
        self.auth.login.assert_not_called()
        body["slider_token"] = self.token()
        success = request(self.app, "POST", "/api/v1/auth/login", body=body)
        self.assertEqual(success.status_code, 200)
        self.assertEqual(success.json()["access_token"], "test-access-token")
        replay = request(self.app, "POST", "/api/v1/auth/login", body=body)
        self.assertEqual(replay.status_code, 400)
        self.auth.login.assert_called_once()

    def test_wrong_password_consumes_verification(self) -> None:
        self.auth.login.side_effect = AuthenticationRequiredError("用户名/邮箱或密码错误")
        body = {"identifier": "student_01", "password": "wrong", "slider_token": self.token()}
        wrong = request(self.app, "POST", "/api/v1/auth/login", body=body)
        self.assertEqual(wrong.status_code, 401)
        replay = request(self.app, "POST", "/api/v1/auth/login", body=body)
        self.assertEqual(replay.status_code, 400)

    def test_invalid_positions_have_safe_validation_errors(self) -> None:
        for position in (-1, 101, 99.9, "100", True):
            response = request(self.app, "POST", "/api/v1/auth/slider/verify", body={
                "challenge_id": "x" * 43, "position": position,
            })
            self.assertEqual(response.status_code, 422)
            self.assertNotIn("challenge_id", response.body.decode())


if __name__ == "__main__":
    unittest.main()
