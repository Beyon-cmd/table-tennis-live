"""Email account and cloud-sync controls."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QVBoxLayout, QWidget)

from services.cloud_sync import CloudSyncManager


class AccountDialog(QDialog):
    def __init__(self, cloud: CloudSyncManager, parent=None):
        super().__init__(parent)
        self.cloud = cloud
        self.setWindowTitle("账号与云端同步")
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(14)

        title = QLabel("关注列表，随账号同行")
        title.setObjectName("AccountTitle")
        layout.addWidget(title)
        self.status = QLabel()
        self.status.setObjectName("AccountNote")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.config_box = QWidget()
        config_form = QFormLayout(self.config_box)
        config_form.setContentsMargins(0, 0, 0, 0)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://项目编号.supabase.co")
        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("publishable / anon key（不要填 secret key）")
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        config_form.addRow("项目 URL", self.url_edit)
        config_form.addRow("公开密钥", self.key_edit)
        self.save_config = QPushButton("连接云端项目")
        self.save_config.setObjectName("AccountPrimary")
        self.save_config.clicked.connect(self._configure)
        config_form.addRow(self.save_config)
        layout.addWidget(self.config_box)

        self.login_box = QWidget()
        login_form = QFormLayout(self.login_box)
        login_form.setContentsMargins(0, 0, 0, 0)
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("邮箱地址")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("密码（不会保存在本机）")
        login_form.addRow("邮箱", self.email_edit)
        login_form.addRow("密码", self.password_edit)
        actions = QHBoxLayout()
        self.login_button = QPushButton("登录")
        self.login_button.setObjectName("AccountPrimary")
        self.signup_button = QPushButton("注册新账号")
        self.signup_button.setObjectName("AccountSecondary")
        actions.addWidget(self.login_button)
        actions.addWidget(self.signup_button)
        login_form.addRow(actions)
        self.login_button.clicked.connect(lambda: self._authenticate(False))
        self.signup_button.clicked.connect(lambda: self._authenticate(True))
        layout.addWidget(self.login_box)

        self.logout_button = QPushButton("退出当前账号")
        self.logout_button.setObjectName("AccountSecondary")
        self.logout_button.clicked.connect(self._logout)
        layout.addWidget(self.logout_button)
        self.note = QLabel("未登录时关注保存在本机；登录后会与该账号的云端列表合并。断网修改会在恢复连接后同步。")
        self.note.setObjectName("AccountNote")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        cloud.auth_finished.connect(self._auth_finished)
        cloud.state_changed.connect(self._state_changed)
        self._refresh()

    def _refresh(self) -> None:
        configured = self.cloud.config is not None
        signed = self.cloud.session is not None
        self.config_box.setVisible(not configured)
        self.login_box.setVisible(configured and not signed)
        self.logout_button.setVisible(signed)
        if signed:
            self.status.setText(f"已登录：{self.cloud.email}\n关注列表正与云端同步。")
        elif configured:
            self.status.setText("登录或注册后，可在其他电脑取回同一账号的关注。")
        else:
            self.status.setText("尚未连接云端项目。先填写项目 URL 和公开密钥；不要使用管理员密钥。")

    def _configure(self) -> None:
        try:
            self.cloud.configure(self.url_edit.text(), self.key_edit.text())
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        self.key_edit.clear()
        self._refresh()

    def _authenticate(self, register: bool) -> None:
        self.login_button.setEnabled(False)
        self.signup_button.setEnabled(False)
        if register:
            self.cloud.sign_up(self.email_edit.text(), self.password_edit.text())
        else:
            self.cloud.sign_in(self.email_edit.text(), self.password_edit.text())

    def _auth_finished(self, success: bool, message: str) -> None:
        self.login_button.setEnabled(True)
        self.signup_button.setEnabled(True)
        self.password_edit.clear()
        self._refresh()
        if self.cloud.session is None or not success:
            self.status.setText(message)

    def _state_changed(self, message: str) -> None:
        if self.isVisible():
            self.status.setText(message)

    def _logout(self) -> None:
        self.cloud.logout()
        self._refresh()
