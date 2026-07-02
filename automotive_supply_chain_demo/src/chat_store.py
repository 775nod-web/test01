"""
チャットスレッド管理（Claude の UI を参考にしたサイドバー履歴機能）

Streamlit の session_state 上にスレッドを保持する:
st.session_state["chat_threads"] = {
    thread_id: {"title": str, "messages": [{"role": "user"|"assistant", "content": str, "context": str|None}]}
}
"""

import uuid
from datetime import datetime

import streamlit as st

THREADS_KEY = "chat_threads"
ACTIVE_THREAD_KEY = "active_thread_id"


def _new_thread_id() -> str:
    return uuid.uuid4().hex[:8]


def init_chat_state():
    if THREADS_KEY not in st.session_state:
        st.session_state[THREADS_KEY] = {}
    if ACTIVE_THREAD_KEY not in st.session_state or (
        st.session_state[ACTIVE_THREAD_KEY] not in st.session_state[THREADS_KEY]
    ):
        create_new_thread()


def create_new_thread() -> str:
    thread_id = _new_thread_id()
    st.session_state[THREADS_KEY][thread_id] = {
        "title": "新しいチャット",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "messages": [],
    }
    st.session_state[ACTIVE_THREAD_KEY] = thread_id
    return thread_id


def get_active_thread_id() -> str:
    return st.session_state[ACTIVE_THREAD_KEY]


def set_active_thread(thread_id: str):
    st.session_state[ACTIVE_THREAD_KEY] = thread_id


def get_threads() -> dict:
    return st.session_state[THREADS_KEY]


def get_active_thread() -> dict:
    return st.session_state[THREADS_KEY][get_active_thread_id()]


def add_message(role: str, content: str, context: str | None = None):
    thread = get_active_thread()
    thread["messages"].append({"role": role, "content": content, "context": context})
    if role == "user" and thread["title"] == "新しいチャット":
        thread["title"] = (content[:24] + "…") if len(content) > 24 else content


def delete_thread(thread_id: str):
    threads = st.session_state[THREADS_KEY]
    if thread_id in threads:
        del threads[thread_id]
    if not threads:
        create_new_thread()
    elif get_active_thread_id() == thread_id:
        set_active_thread(next(iter(threads.keys())))
