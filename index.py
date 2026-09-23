import os
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import streamlit as st
from streamlit_ace import st_ace
from dotenv import load_dotenv

from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

import chromadb

load_dotenv()

# ---------------------------------------------------------------------------
# Config / sandboxed directories
# ---------------------------------------------------------------------------
WORKSPACE_DIR = Path("workspace")
WORKSPACE_DIR.mkdir(exist_ok=True)

MEMORY_DIR = Path("memory_store")
MEMORY_DIR.mkdir(exist_ok=True)

# Persistent client -> data survives app restarts (this IS your cross-session memory)
chroma_client = chromadb.PersistentClient(path=str(MEMORY_DIR))
memory_collection = chroma_client.get_or_create_collection(name="agent_memory")


def _safe_path(filename: str) -> Path:
    """Resolve a filename inside WORKSPACE_DIR only — blocks path traversal
    (e.g. '../../etc/passwd')."""
    base = WORKSPACE_DIR.resolve()
    target = (WORKSPACE_DIR / filename).resolve()
    if base != target and base not in target.parents:
        raise ValueError("Access outside the workspace directory is not allowed.")
    return target


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
@tool
def read_file(filename: str) -> str:
    """Read and return the text contents of a file inside the agent's workspace.
    Only files within the workspace directory are accessible."""
    try:
        path = _safe_path(filename)
        if not path.exists():
            return f"Error: file '{filename}' does not exist in the workspace."
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading file: {e}"


@tool
def write_file(filename: str, content: str) -> str:
    """Write text content to a file inside the agent's workspace. Creates the
    file if it doesn't exist, or overwrites it if it does."""
    try:
        path = _safe_path(filename)
        path.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} characters to {filename}."
    except Exception as e:
        return f"Error writing file: {e}"


@tool
def execute_python_code(code: str, timeout_seconds: int = 10) -> str:
    """Write the given Python code to a temp file and execute it in an isolated
    subprocess (not exec/eval in-process). Returns stdout, stderr, and exit code.
    Execution is killed after timeout_seconds to prevent runaway loops."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, dir=WORKSPACE_DIR
    ) as f:
        f.write(code)
        script_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=WORKSPACE_DIR,
        )
        return (
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}\n"
            f"--- exit code: {result.returncode} ---"
        )
    except subprocess.TimeoutExpired:
        return f"Error: execution timed out after {timeout_seconds} seconds."
    except Exception as e:
        return f"Error executing code: {e}"
    finally:
        try:
            os.remove(script_path)
        except OSError:
            pass


@tool
def save_memory(fact: str) -> str:
    """Save a fact or piece of information to long-term memory that persists
    across sessions (not just this conversation thread). Use this when the
    user shares something worth remembering for next time."""
    memory_id = str(uuid.uuid4())
    memory_collection.add(documents=[fact], ids=[memory_id])
    return f"Saved to long-term memory: {fact}"


@tool
def recall_memory(query: str, n_results: int = 3) -> str:
    """Search long-term memory for facts relevant to the query. Use this at
    the start of a task to check for relevant context from past sessions."""
    count = memory_collection.count()
    if count == 0:
        return "No memories stored yet."
    results = memory_collection.query(
        query_texts=[query], n_results=min(n_results, count)
    )
    docs = results.get("documents", [[]])[0]
    if not docs:
        return "No relevant memories found."
    return "\n".join(f"- {d}" for d in docs)


TOOLS = [read_file, write_file, execute_python_code, save_memory, recall_memory]

# ---------------------------------------------------------------------------
# Agent (cached so it isn't rebuilt on every Streamlit rerun)
# ---------------------------------------------------------------------------
@st.cache_resource
def get_agent():
    model = ChatGroq(model="openai/gpt-oss-120b", temperature=0)
    checkpointer = InMemorySaver()  # per-thread chat memory (separate from the long-term memory tool)
    return create_agent(
        model=model,
        tools=TOOLS,
        system_prompt=(
            "You are an autonomous agent with tool access. You can read/write files "
            "in your workspace, execute Python code in a sandboxed subprocess, and "
            "save/recall long-term memory that persists across sessions. "
            "Call recall_memory when past context might help. Call save_memory when "
            "the user shares something worth remembering. "
            "IMPORTANT: whenever you write any Python code, you MUST call write_file "
            "to save it (use filename 'scratch.py' unless the user names one) BEFORE "
            "calling execute_python_code or replying. Never paste code only in your "
            "chat reply without also writing it to a file — the file is what the UI's "
            "code editor displays. Never claim code ran without actually executing it."
        ),
        checkpointer=checkpointer,
    )


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Tool-Use Agent", layout="wide")
st.title("🤖 AI Agent — File I/O, Code Execution, Long-Term Memory")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "last_code" not in st.session_state:
    st.session_state.last_code = (
        "# Code the agent writes (via write_file) will appear here.\n"
        "# You can edit it and click 'Run code manually' to re-execute.\n"
    )

agent = get_agent()

chat_col, editor_col = st.columns([1, 1])

with chat_col:
    st.subheader("Chat")

    # uploaded = st.file_uploader("Give the agent a file", key="uploader")
    # if uploaded is not None:
    #     dest = WORKSPACE_DIR / uploaded.name
    #     dest.write_bytes(uploaded.getvalue())
    #     st.caption(f"Saved to workspace as '{uploaded.name}' — ask the agent to read_file it.")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("Ask the agent to do something...")
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        config = {"configurable": {"thread_id": st.session_state.thread_id}}
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                result = agent.invoke(
                    {"messages": [{"role": "user", "content": user_input}]},
                    config=config,
                )
                final_message = result["messages"][-1].content
                st.markdown(final_message)

                # If the agent wrote code via write_file, pull it into the editor
                wrote_via_tool = False
                for m in result["messages"]:
                    tool_calls = getattr(m, "tool_calls", None)
                    if not tool_calls:
                        continue
                    for tc in tool_calls:
                        if tc["name"] == "write_file" and "content" in tc.get("args", {}):
                            st.session_state.last_code = tc["args"]["content"]
                            wrote_via_tool = True

                # Fallback: agent replied with a code block but never called write_file
                if not wrote_via_tool:
                    match = re.search(r"```(?:python)?\n(.*?)```", final_message, re.DOTALL)
                    if match:
                        st.session_state.last_code = match.group(1).strip()

        st.session_state.messages.append({"role": "assistant", "content": final_message})

with editor_col:
    st.subheader("Code Editor")
    code = st_ace(
        value=st.session_state.last_code,
        language="python",
        theme="monokai",
        keybinding="vscode",
        font_size=14,
        tab_size=4,
        show_gutter=True,
        wrap=False,
        auto_update=False,  # only pushes value on blur / Ctrl+Enter, not every keystroke
        height=400,
        key="ace_editor",
    )
    st.session_state.last_code = code

    if st.button("▶ Run code manually"):
        output = execute_python_code.invoke({"code": code})
        st.code(output, language="text")

    st.divider()
    st.subheader("Long-Term Memory")
    if memory_collection.count() == 0:
        st.caption("No memories stored yet.")
    else:
        for doc in memory_collection.get()["documents"]:
            st.markdown(f"- {doc}")