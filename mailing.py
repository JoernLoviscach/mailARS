#    Copyright (C) 2020 Jörn Loviscach <https://j3L7h.de>
#
#    This file is part of mailARS.
#
#    mailARS is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    mailARS is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with mailARS.  If not, see <https://www.gnu.org/licenses/>.

from __future__ import annotations
import typing
import PyQt5.QtCore as core
import PyQt5.QtWidgets as widgets
import PyQt5.QtGui as gui
import smtplib
import ssl
import email
import email.utils
from email.policy import default
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
import datetime
import time
import imaplib
import re
import graphics
import preferences
import mailboxes_window
import drawing_window


def _format_exception(ex: Exception) -> str:
    error_string: str = ""
    if hasattr(ex, "args"):
        parts = []
        for arg in ex.args:
            try:
                parts.append(arg.decode())
            except (UnicodeDecodeError, AttributeError):
                parts.append(str(arg))
        error_string = "; ".join(parts)
    else:
        error_string = str(ex)
    return error_string

class _SenderSignals(core.QObject):
    # can't do this on _SenderRunnable because QRunnable does not inherit from QObject.
    status_updated: core.pyqtSignal = core.pyqtSignal(str, name="statusUpdated")
    status_changed: core.pyqtSignal = core.pyqtSignal(bool, name="statusChanged")

_sender_signals = _SenderSignals()

class _SenderRunnable(core.QRunnable):
    def __init__(self, \
    addresses: typing.List[str], \
    elements: typing.List[graphics.GraphicsObject], \
    when: datetime.datetime, \
    message_id: str, \
    name: str, \
    smtp_sender: str, \
    smtp_server: str, \
    password: str) -> None:
        super().__init__()
        self._addresses = addresses
        self._elements = elements
        self._when = when
        self._message_id = message_id
        self._name = name
        self._smtp_sender = smtp_sender
        self._smtp_server = smtp_server
        self._password = password

    def run(self) -> None:
        try:
            import pydevd
            pydevd.settrace(suspend=False)  # to enable debugging
        except:
            pass

        server: typing.Optional[smtplib.SMTP] = None
        try:
            if self._name == "" or self._smtp_sender == "" or self._password == "":
                raise RuntimeError(self.tr("SMTP settings are incomplete."))
            if len(self._addresses) == 0:
                raise RuntimeError(self.tr("No addressees available"))

            _sender_signals.status_updated.emit(self.tr("Sending"))

            text, files = graphics.serialize(self._elements)

            message = MIMEMultipart()
            message["From"] = email.utils.formataddr((self._name, self._smtp_sender))
            message["To"] = ", ".join(self._addresses)
            message["Subject"] = "mailARS, not intended for reading"
            message["Date"] = email.utils.format_datetime(self._when)
            message["X-MailARS-Message-ID"] = self._message_id
            message.attach(MIMEText("Alles in Attachments!", "plain"))
            elementsAttachment = MIMEText(text, "plain", "utf-8")
            elementsAttachment.add_header("Content-Disposition", "attachment; filename= elements.txt")
            message.attach(elementsAttachment)
            for name, data in files.items():
                imageAttachment = MIMEImage(data.data())
                imageAttachment.add_header("Content-Disposition", "attachment; filename= " + name)
                message.attach(imageAttachment)

            context = ssl.create_default_context()
        
            server = smtplib.SMTP(self._smtp_server, 587)
            server.ehlo()  # could be omitted
            server.starttls(context=context)
            server.ehlo()  # could be omitted
            server.login(self._smtp_sender, self._password)
            server.sendmail(self._smtp_sender, self._addresses, message.as_string())
            _sender_signals.status_updated.emit("")
        except Exception as ex:
            _sender_signals.status_updated.emit(_format_exception(ex))
        finally:
            _sender_signals.status_changed.emit(True)
            if server is not None:
                server.quit()
    
# The content of addresses and elements must not change during sending!
# Hence, only send the outbox clone of a message.
def send(mailboxes_win: mailboxes_window.MailboxesWindow, \
    drawing_win: drawing_window.DrawingWindow, \
    addresses: typing.List[str], \
    elements: typing.List[graphics.GraphicsObject], \
    when: datetime.datetime, \
    message_id: str, \
    name: str, \
    smtp_sender: str, \
    smtp_server: str, \
    password: str) -> None:

    sender = _SenderRunnable(addresses, elements, when, message_id, name, smtp_sender, smtp_server, password)
    _sender_signals.status_updated.connect(mailboxes_win.display_on_status_bar)
    _sender_signals.status_changed.connect(drawing_win.set_send_mail_status)
    _sender_signals.status_changed.emit(False)
    core.QThreadPool.globalInstance().start(sender)

class _ReceiverThread(core.QThread):
    status_updated: core.pyqtSignal = core.pyqtSignal(str, name="statusUpdated")
    got_mail: core.pyqtSignal = core.pyqtSignal(name="gotMail")
    mail_fetched: core.pyqtSignal = core.pyqtSignal(str, str, list, datetime.datetime, str, name="mailFetched")
    status_changed: core.pyqtSignal = core.pyqtSignal(bool, name="statusChanged")

    def __init__(self, parent: mailboxes_window.MailboxesWindow) -> None:
        super().__init__(parent)
        self._user: str = ""
        self._server: str = ""
        self._password: str = ""
        self._need_to_change_connection: bool = False
        self._need_to_fetch: bool = False
        self._known_message_ids: typing.List[str] = []
        self._connection_data_mutex: core.QMutex = core.QMutex()

    def run(self) -> None:
        try:
            import pydevd
            pydevd.settrace(suspend=False)  # to enable debugging
        except:
            pass

        user = ""
        server = ""
        password = ""
        need_to_change_connection = True
        need_to_fetch = False
        known_message_ids: typing.List[str] = []
        connection: typing.Optional[imaplib.IMAP4_SSL] = None
        previous_request_time = time.perf_counter()
        first_request = True

        forbidden_characters_in_names = re.compile(r"[^a-zA-Z0-9@\-\.]")

        while(True):
            need_to_stop = self.isInterruptionRequested()
            current_request_time = time.perf_counter()

            if not need_to_stop:
                with core.QMutexLocker(self._connection_data_mutex):
                    user = self._user
                    server = self._server
                    password = self._password
                    need_to_change_connection = self._need_to_change_connection
                    self._need_to_change_connection = False
                    need_to_fetch = self._need_to_fetch
                    known_message_ids  = self._known_message_ids

                    self._need_to_fetch = False

            if need_to_change_connection or need_to_stop:
                if connection is not None:
                    # close IMAP
                    try:
                        connection.close()
                        connection.logout()
                    except Exception as ex:
                        self.status_updated.emit(_format_exception(ex))
                    connection = None

            if need_to_stop:
                self.quit()
                return
            else:
                if need_to_change_connection or need_to_fetch and connection is None:
                    need_to_change_connection = False
                    # open IMAP
                    try:
                        connection = imaplib.IMAP4_SSL(server)
                        connection.login(user, password)

                        # Does the mailARS IMAP folder for processed messages exist already?
                        # If not, create it.
                        typ, data = connection.list(pattern="mailARS")
                        if typ != "OK":
                            raise RuntimeError(self.tr("IMAP List failed."))
                        if data[0] is None or not data[0].decode().endswith("mailARS"):
                            typ, data = connection.create("mailARS")
                            if typ != "OK":
                                raise RuntimeError(self.tr("IMAP Create failed."))

                        connection.select("INBOX")
                        first_request = True
                    except Exception as ex:
                        self.status_updated.emit(_format_exception(ex))
                        if connection is not None:
                            try:
                                connection.close()
                                connection.logout()
                            except:
                                pass
                            connection = None
                if connection is not None:
                    if need_to_fetch:
                        need_to_fetch = False
                        previous_request_time = current_request_time
                        try:
                            # Note that FETCH sets SEEN flag.
                            req = '(SUBJECT "mailARS, not intended for reading" UNSEEN)'
                            if first_request:
                                req = '(SUBJECT "mailARS, not intended for reading")'
                                first_request = False
                            typ, data = connection.search(None, req)
                            if typ != "OK":
                                raise RuntimeError(self.tr("IMAP Search failed."))
                            nums = data[0].decode().split()
                            count = len(nums)
                            for num in nums: # num is the UID
                                self.status_updated.emit(self.tr("Fetching mail:") + " " + str(count))
                                count -= 1

                                typ, data = connection.fetch(num, "(BODY.PEEK[HEADER])")                            
                                if typ != "OK":
                                    raise RuntimeError(self.tr("IMAP Peek failed."))
                                msg = email.message_from_bytes(typing.cast(bytes, data[0][1]), policy=default)
                                
                                if msg["Subject"] != "mailARS, not intended for reading":  # IMAP only does substring matching
                                    continue

                                if "X-MailARS-Message-ID" in msg and len(msg["X-MailARS-Message-ID"]) > 10:
                                    message_id = str(msg["X-MailARS-Message-ID"])
                                else:
                                    message_id = str(msg["Message-ID"])
                                # message_id may contain dangerous stuff such as "..\..\".
                                # Hence, sanitize:
                                message_id = forbidden_characters_in_names.sub("_", message_id)
                                
                                if message_id in known_message_ids:
                                    continue

                                typ, data = connection.fetch(num, "(BODY[])")                            
                                if typ != "OK":
                                    raise RuntimeError(self.tr("IMAP Fetch failed."))
                                message_data = typing.cast(bytes, data[0][1])
                                msg = email.message_from_bytes(message_data, policy=default)

                                name, address = email.utils.parseaddr(msg["From"])
                                if address == "":
                                    name += " " + self.tr("(Error in address)")
                                when = email.utils.parsedate_to_datetime(msg["Date"])

                                #TODO: Handle replies that are standard text mails or PDF attachments.
                                document_text: str = ""
                                files: typing.Dict[str, core.QByteArray] = {}
                                for part in msg.walk():
                                    if part.get_content_disposition() == "attachment":
                                        filename = part.get_filename()
                                        # The filenname may contain dangerous stuff such as "..\..\".
                                        # Hence:
                                        if forbidden_characters_in_names.search(filename) is not None:
                                            # TODO: message to user
                                            pass
                                        else:
                                            if filename == "elements.txt":
                                                document_text = part.get_payload(decode=True).decode()
                                            elif filename.endswith(".jpg") or filename.endswith(".jpeg") or filename.endswith(".png"):
                                                files[filename] = part.get_payload(decode=True)
                                if document_text != "":
                                    elements = graphics.deserialize(document_text, files)
                                else:
                                    continue
                                    #TODO

                                self.mail_fetched.emit(address, name, elements, when, message_id)

                                # Move the message to the mailARS folder
                                typ, data = connection.copy(num, "mailARS")                            
                                if typ != "OK":
                                    raise RuntimeError(self.tr("IMAP UID Copy failed."))
                                typ, data = connection.store(num , "+FLAGS", r"\Deleted")
                                if typ != "OK":
                                    raise RuntimeError(self.tr("IMAP UID Store failed."))

                            typ, data = connection.expunge()
                            if typ != "OK":
                                raise RuntimeError(self.tr("IMAP Expunge failed."))
                            self.status_updated.emit("")
                        except Exception as ex:
                            self.status_updated.emit(_format_exception(ex))
                            try:
                                connection.close()
                                connection.logout()
                            except:
                                pass
                            connection = None
                        self.status_changed.emit(True)
                    elif current_request_time - previous_request_time > 60.0:
                        previous_request_time = current_request_time
                        try:
                            # connection.idle() would be the standard way
                            # but does (on our system) not seem to return
                            # the status update described in RFC 3501 6.1.2.
                            typ, data = connection.recent()
                            try:
                                if data[0] is not None and data[0].decode() != "0":
                                    self.got_mail.emit()
                            except:
                                pass
                        except Exception as ex:
                            self.status_updated.emit(_format_exception(ex))
                            try:
                                connection.close()
                                connection.logout()
                            except:
                                pass
                            connection = None
            self.msleep(300)

    # should also be called once before the thread starts
    def update_receiver_connection_data(self, user: str, server: str, password: str) -> None:
        if user == "" or server == "":
            self.status_updated.emit(self.tr("IMAP settings are incomplete."))
            return
        if password == "":
            self.status_updated.emit(self.tr("The mail password cannot be empty."))
            return
        with core.QMutexLocker(self._connection_data_mutex):
            self._user = user
            self._server = server
            self._password = password
            self._need_to_change_connection = True

    def fetch(self, known_message_ids: typing.List[str]) -> None:
        with core.QMutexLocker(self._connection_data_mutex):
            self._need_to_fetch = True
            self._known_message_ids = known_message_ids
        
_receiver: typing.Optional[_ReceiverThread] = None            

def start_receiver(mbw: mailboxes_window.MailboxesWindow) -> None:
    global _receiver
    if _receiver is not None:
        return
    _receiver = _ReceiverThread(mbw)
    _receiver.status_updated.connect(mbw.display_on_status_bar)
    _receiver.got_mail.connect(mbw.got_mail)
    _receiver.mail_fetched.connect(mbw.add_mail)
    _receiver.status_changed.connect(mbw.set_fetch_mail_status)

    preferences.attach_update_receiver_connection_data_listener(_receiver)
    # for the initial setting:
    _receiver.update_receiver_connection_data(preferences.get("imap_user"), \
        preferences.get("imap_server"), \
        preferences.get_password())
    _receiver.start()

def stop_receiver() -> None:
    global _receiver
    if _receiver is None:
        return
    preferences.detach_update_receiver_connection_data_listener(_receiver)
    _receiver.requestInterruption()
    _receiver.wait()
    _receiver = None

def update_receiver_connection_data(user: str, server: str, password: str):
    if _receiver is not None:
        _receiver.update_receiver_connection_data(user, server, password)

def fetch(known_message_ids: typing.List[str]):
    if _receiver is not None:
        _receiver.status_changed.emit(False)
        _receiver.fetch(known_message_ids)
