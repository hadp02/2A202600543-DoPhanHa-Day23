"""Script tương tác trực tiếp với LangGraph Agent."""

import uuid
from langgraph_agent_lab.graph import build_graph
from langgraph_agent_lab.persistence import build_checkpointer
from langgraph_agent_lab.state import Route, Scenario, initial_state


def main():
    print("🚀 Đang khởi tạo LangGraph Agent cùng DeepSeek V4 Flash...")
    checkpointer = build_checkpointer("memory")
    graph = build_graph(checkpointer=checkpointer)

    print("\n💡 Bạn có thể đặt câu hỏi cho Agent (Nhập 'exit' hoặc 'quit' để thoát)")
    print("   Gợi ý 1: Làm thế nào để đổi mật khẩu? (Simple route)")
    print("   Gợi ý 2: Kiểm tra trạng thái đơn hàng #12345 (Tool route)")
    print("   Gợi ý 3: Hoàn tiền ngay cho khách hàng này! (Risky route)")
    print("-" * 65)

    while True:
        try:
            query = input("\n👤 Bạn: ").strip()
            if not query:
                continue
            if query.lower() in ["exit", "quit", "thoát"]:
                print("👋 Tạm biệt!")
                break

            scenario = Scenario(
                id=str(uuid.uuid4())[:8], query=query, expected_route=Route.SIMPLE
            )
            state = initial_state(scenario)
            config = {"configurable": {"thread_id": state["thread_id"]}}

            print("🤖 Agent đang suy nghĩ và phân loại...")
            result = graph.invoke(state, config=config)

            route = result.get("route", "N/A")
            risk = result.get("risk_level", "N/A")
            print(f"📌 Phân loại luồng (Route): [{route.upper()}] | Rủi ro: {risk}")

            if result.get("tool_results"):
                print(f"🛠️ Kết quả Tool: {result['tool_results'][-1]}")

            ans = result.get("final_answer") or result.get("pending_question")
            print(f"💬 Agent trả lời:\n   {ans}")

        except KeyboardInterrupt:
            print("\n👋 Tạm biệt!")
            break
        except Exception as e:
            print(f"❌ Có lỗi xảy ra: {e}")


if __name__ == "__main__":
    main()
