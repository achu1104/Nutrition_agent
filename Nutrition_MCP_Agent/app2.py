
import os
import json
import asyncio
from pathlib import Path

import streamlit as st
from groq import Groq
from dotenv import load_dotenv

from mcp_client import discover_tools, call_mcp_tool

load_dotenv(Path(__file__).resolve().parent / ".env")

st.set_page_config(
    page_title="Nutrition AI MCP Agent",
    page_icon="🥗",
    layout="wide"
)

st.title("🥗 Nutrition AI Agent with MCP")
st.caption("Streamlit + Groq + MCP Client + MCP Server")

api_key = os.getenv("GROQ_API_KEY")
model_name = os.getenv(
    "GROQ_MODEL", "llama-3.3-70b-versatile"
)

if not api_key:
    st.error("Add GROQ_API_KEY to your .env file.")
    st.stop()

client = Groq(api_key=api_key)

# User information
st.sidebar.header("User Information")

age = st.sidebar.number_input(
    "Age", min_value=1, max_value=120, value=22
)

weight = st.sidebar.number_input(
    "Weight (kg)", min_value=1.0, value=60.0
)

height = st.sidebar.number_input(
    "Height (cm)", min_value=1.0, value=160.0
)

goal = st.sidebar.selectbox(
    "Goal",
    ["Maintain Weight", "Weight Loss", "Muscle Gain"]
)

# Initialize conversation memory
if "messages" not in st.session_state:
    st.session_state.messages = []

if "tool_history" not in st.session_state:
    st.session_state.tool_history = []

# MCP connection and tool discovery
try:
    discovered = asyncio.run(discover_tools())
except Exception as e:
    st.error(f"MCP connection failed: {e}")
    st.stop()

st.sidebar.success("MCP Server Connected")

st.sidebar.subheader("Discovered MCP Tools")

for tool in discovered:
    st.sidebar.write("✅", tool["name"])

# Convert discovered MCP tools into Groq tools
groq_tools = []

for tool in discovered:
    groq_tools.append({
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["parameters"]
        }
    })

system_prompt = f"""
You are a helpful Nutrition AI Agent.

User information:
Age: {age}
Weight: {weight} kg
Height: {height} cm
Goal: {goal}

Rules:
1. Remember context from the conversation.
2. For calorie questions, use get_calories.
3. For protein questions, use get_protein.
4. If both are requested, call both tools.
5. Do not invent nutrition values.
6. If food is unavailable, explain that clearly.
7. Use MCP results to provide accurate answers.
8. Give general nutrition guidance when appropriate.
9. Do not present estimates as medical diagnoses.
10. Never claim a tool was used unless it was called.
"""

st.subheader("Chat with Nutrition AI")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

question = st.chat_input(
    "Ask about calories, protein or nutrition..."
)

if question:
    st.session_state.messages.append({
        "role": "user",
        "content": question
    })

    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking and checking MCP tools..."):
            try:
                messages = [
                    {
                        "role": "system",
                        "content": system_prompt
                    }
                ] + st.session_state.messages.copy()

                tool_logs = []
                final_answer = None

                for _ in range(5):
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=messages,
                        tools=groq_tools if groq_tools else None,
                        tool_choice="auto" if groq_tools else "none"
                    )

                    assistant_message = response.choices[0].message

                    messages.append(
                        assistant_message.model_dump(
                            exclude_none=True
                        )
                    )

                    if not assistant_message.tool_calls:
                        final_answer = assistant_message.content
                        break

                    for tool_call in assistant_message.tool_calls:
                        name = tool_call.function.name
                        arguments = json.loads(
                            tool_call.function.arguments
                        )

                        allowed = {
                            tool["name"] for tool in discovered
                        }

                        if name not in allowed:
                            result = "Tool not available"
                        else:
                            try:
                                result = asyncio.run(
                                    call_mcp_tool(name, arguments)
                                )
                            except Exception as e:
                                result = f"Tool error: {e}"

                        tool_logs.append({
                            "tool": name,
                            "arguments": arguments,
                            "result": result
                        })

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result
                        })

                if final_answer is None:
                    final_answer = (
                        "Unable to finish the tool sequence. "
                        "Please try a simpler question."
                    )

                st.write(final_answer)

                if tool_logs:
                    with st.expander("MCP Tool Execution Results"):
                        for log in tool_logs:
                            st.write("Tool:", log["tool"])
                            st.json(log["arguments"])
                            st.code(log["result"])

                st.session_state.tool_history.extend(tool_logs)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": final_answer
                })

            except Exception as e:
                st.error(f"Agent error: {e}")

# Tool execution history
st.divider()
st.subheader("MCP Tool Call History")

if st.session_state.tool_history:
    for i, log in enumerate(st.session_state.tool_history, 1):
        with st.expander(f"Call {i}: {log['tool']}"):
            st.json(log["arguments"])
            st.write(log["result"])
else:
    st.info("No MCP tools have been called yet.")

if st.sidebar.button("Clear Conversation"):
    st.session_state.messages = []
    st.session_state.tool_history = []
    st.rerun()
