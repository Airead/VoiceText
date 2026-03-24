"""Tests for vt.notify API."""

from unittest.mock import patch

from wenzi.scripting.api.notify import notify


class TestNotify:
    @patch("wenzi.statusbar.send_notification")
    def test_notify(self, mock_send):
        notify("Title", "Message")
        mock_send.assert_called_once_with("Title", "", "Message", sound="default")

    @patch("wenzi.statusbar.send_notification")
    def test_notify_no_message(self, mock_send):
        notify("Title")
        mock_send.assert_called_once_with("Title", "", "", sound="default")

    @patch("wenzi.statusbar.send_notification")
    def test_notify_custom_sound(self, mock_send):
        notify("Title", "Message", sound="Glass")
        mock_send.assert_called_once_with("Title", "", "Message", sound="Glass")

    @patch("wenzi.statusbar.send_notification")
    def test_notify_silent(self, mock_send):
        notify("Title", "Message", sound=None)
        mock_send.assert_called_once_with("Title", "", "Message", sound=None)
