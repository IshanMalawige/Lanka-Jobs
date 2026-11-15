import requests
import unittest
from unittest.mock import Mock, patch

from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Job, TelegramNotification
from app.services.telegram_notifier import queue_high_match_job, send_pending_notifications


class TelegramNotificationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    @patch("app.services.telegram_notifier.get_profile", return_value={"skills": ["python", "sql", "linux"]})
    @patch("app.services.telegram_notifier.requests.post")
    def test_sends_once_for_new_jobs_strictly_above_threshold(self, post, _profile):
        response = Mock()
        response.json.return_value = {"ok": True}
        post.return_value = response
        matching = Job(
            title="Python SQL Engineer",
            company="Example Co",
            category="IT",
            source="itpro",
            url="https://example.com/high-match",
            description="Python SQL",
        )
        threshold = Job(
            title="Python SQL Linux Windows Server role",
            category="IT",
            source="itpro",
            url="https://example.com/exactly-75",
            description="Python SQL Linux Windows Server",
        )
        self.session.add_all([matching, threshold])
        self.session.commit()

        with (
            patch("app.services.telegram_notifier.settings.telegram_bot_token", SecretStr("test-token")),
            patch("app.services.telegram_notifier.settings.telegram_chat_id", "123456"),
            patch("app.services.telegram_notifier.settings.telegram_match_threshold", 75),
        ):
            self.assertTrue(queue_high_match_job(self.session, matching))
            self.assertFalse(queue_high_match_job(self.session, threshold))
            self.assertEqual(send_pending_notifications(self.session), 1)
            self.assertFalse(queue_high_match_job(self.session, matching))
            self.assertEqual(send_pending_notifications(self.session), 0)

        post.assert_called_once()
        self.assertIn("/bottest-token/sendMessage", post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs["json"]["chat_id"], "123456")
        self.assertIn("High-match job (100%)", post.call_args.kwargs["json"]["text"])
        self.assertIn("https://example.com/high-match", post.call_args.kwargs["json"]["text"])
        self.assertEqual(
            self.session.query(TelegramNotification).filter_by(status="sent").count(),
            1,
        )

    @patch("app.services.telegram_notifier.requests.post")
    def test_does_not_queue_without_bot_configuration(self, post):
        job = Job(
            title="Python role",
            category="IT",
            source="itpro",
            url="https://example.com/python",
            description="Python",
        )
        self.session.add(job)
        self.session.commit()

        with (
            patch("app.services.telegram_notifier.settings.telegram_bot_token", SecretStr("")),
            patch("app.services.telegram_notifier.settings.telegram_chat_id", ""),
        ):
            self.assertFalse(queue_high_match_job(self.session, job))
            self.assertEqual(send_pending_notifications(self.session), 0)

        post.assert_not_called()
        self.assertEqual(self.session.query(TelegramNotification).count(), 0)

    @patch("app.services.telegram_notifier.get_profile", return_value={"skills": ["python"]})
    @patch("app.services.telegram_notifier.requests.post")
    def test_retries_pending_message_after_transport_failure(self, post, _profile):
        response = Mock()
        response.json.return_value = {"ok": True}
        post.side_effect = requests.Timeout("temporary timeout")
        job = Job(
            title="Python role",
            category="IT",
            source="itpro",
            url="https://example.com/python",
            description="Python",
        )
        self.session.add(job)
        self.session.commit()

        with (
            patch("app.services.telegram_notifier.settings.telegram_bot_token", SecretStr("test-token")),
            patch("app.services.telegram_notifier.settings.telegram_chat_id", "123456"),
        ):
            self.assertTrue(queue_high_match_job(self.session, job))
            self.assertEqual(send_pending_notifications(self.session), 0)
            self.assertEqual(
                self.session.query(TelegramNotification).filter_by(status="pending").count(),
                1,
            )
            post.side_effect = None
            post.return_value = response
            self.assertEqual(send_pending_notifications(self.session), 1)

        self.assertEqual(
            self.session.query(TelegramNotification).filter_by(status="sent").count(),
            1,
        )


if __name__ == "__main__":
    unittest.main()
