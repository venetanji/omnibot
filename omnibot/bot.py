from typing import Annotated, Literal, TypedDict
from typing import List
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph, MessagesState
from langgraph.prebuilt import ToolNode
from tools import get_weather

tools = [get_weather]
tool_node = ToolNode(tools)

llm = ChatOllama(model="venetanji/llama3.2-tool", base_url="http://localhost:11434").bind_tools(tools)

def should_continue(state: MessagesState) -> Literal["tools", END]:
    messages = state['messages']
    last_message = messages[-1]
    # If the LLM makes a tool call, then we route to the "tools" node
    if last_message.tool_calls:
        print(last_message.tool_calls)
        # remove the last message
        return "tools"
    # Otherwise, we stop (reply to the user)
    return END

# Define the function that calls the model
def call_model(state: MessagesState):
    messages = state['messages']
    response = llm.invoke(messages)
    # We return a list, because this will get added to the existing list
    return {"messages": [response]}

# Define a new graph
graph_builder = StateGraph(MessagesState)

# Define the two nodes we will cycle between
graph_builder.add_node("agent", call_model)
graph_builder.add_node("tools", tool_node)

# Set the entrypoint as `agent`
# This means that this node is the first one called
graph_builder.add_edge(START, "agent")

# We now add a conditional edge
graph_builder.add_conditional_edges(
    # First, we define the start node. We use `agent`.
    # This means these are the edges taken after the `agent` node is called.
    "agent",
    # Next, we pass in the function that will determine which node is called next.
    should_continue,
    ["tools", END]
)

# We now add a normal edge from `tools` to `agent`.
# This means that after `tools` is called, `agent` node is called next.
graph_builder.add_edge("tools", 'agent')

# Initialize memory to persist state between graph runs
checkpointer = MemorySaver()

# Finally, we compile it!
# This compiles it into a LangChain Runnable,
# meaning you can use it as you would any other runnable.
# Note that we're (optionally) passing the memory when compiling the graph
graph = graph_builder.compile(checkpointer=checkpointer)
