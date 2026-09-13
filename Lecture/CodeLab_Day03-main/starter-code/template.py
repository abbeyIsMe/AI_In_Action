"""
Lab #3: Baseline Chatbot vs ReAct Agent
Học viên hoàn thiện các mục TODO để hoàn thành bài lab.
"""

import json
import re
from tools import TOOL_DEFINITIONS, TOOL_MAP, get_flight_info, get_weather_forecast

SYSTEM_PROMPT = """Bạn là một ReAct Agent thông minh hỗ trợ khách hàng Vingroup.
Bạn chỉ sử dụng các công cụ sau:
{tools}

Quy trình trả lời bắt buộc:
Thought: <Suy nghĩ bước tiếp theo>
Action: {{"name": "<tên tool>", "args": {{<tham số>}}}}
Observation: <Kết quả từ tool>
... (Lặp lại cho tới khi có đủ dữ liệu)
Final Answer: <Câu trả lời hoàn chỉnh cho khách hàng>
"""

class ChatbotBaseline:
    """Baseline LLM Chatbot (Không sử dụng ReAct Loop hay Tools)"""
    def query(self, user_input: str) -> str:
        # TODO: Trả về câu trả lời tĩnh hoặc gọi LLM 1 lượt (không dùng tool)
        return {
            "status": "success",
            "answer": f"[Chatbot Baseline] Trả lời cho: {user_input}",
            "tool_calls": []
        }

class ReActAgent:
    """ReAct Agent có sử dụng Thought-Action-Observation Loop"""
    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.trace = []

    def run(self, user_input: str) -> str:
        # TODO 1: Khởi tạo mảng lưu lịch sử conversation / traces
        # TODO 2: Thiết lập vòng lặp while iteration < self.max_iterations
        # TODO 3: Phân tích Thought / Action từ Agent
        # TODO 4: Thực thi Tool trong TOOL_MAP nếu có Action
        # TODO 5: Ghi lại Observation và lặp lại cho tới khi ra Final Answer
        self.trace = []
        actions = []
        upper_input = user_input.upper()
        airport_codes = re.findall(r"\b[A-Z]{3}\b", upper_input)

        flight_match = re.search(
            r"(?:TỪ|FROM)\s+([A-Z]{3})\s+(?:ĐI|ĐẾN|TO)\s+([A-Z]{3})",
            upper_input
        )
        if flight_match:
            price_match = re.search(
                r"(?:DƯỚI|THẤP HƠN|TỐI ĐA|UNDER|BELOW)\s*"
                r"([\d.,]+)\s*(TRIỆU|MILLION|M)?",
                upper_input
            )
            max_price = 5000000
            if price_match:
                amount = float(price_match.group(1).replace(",", "."))
                if price_match.group(2) in ("TRIỆU", "MILLION"):
                    amount *= 1000000
                max_price = int(amount)
            actions.append({
                "name": "get_flight_info",
                "args": {
                    "origin": flight_match.group(1),
                    "destination": flight_match.group(2),
                    "max_price": max_price
                }
            })

        weather_code = next(
            (code for code in reversed(airport_codes) if code in {"SGN", "HAN", "DAD"}),
            None
        )
        if weather_code and re.search(
            r"THỜI TIẾT|MẶC GÌ|NÊN MẶC|WEATHER", upper_input
        ):
            actions.append({
                "name": "get_weather_forecast",
                "args": {"city_code": weather_code}
            })

        observations = []
        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            if not actions:
                answer = (
                    "Chính sách đổi trả vé máy bay Vinpearl được áp dụng "
                    "theo điều kiện của từng loại vé. Vui lòng kiểm tra "
                    "điều kiện vé hoặc liên hệ bộ phận hỗ trợ."
                    if "VINPEARL" in upper_input
                    else f"[ReAct Agent] Tôi chưa tìm thấy công cụ phù hợp cho: {user_input}"
                )
                self.trace.append({
                    "step": iteration,
                    "thought": "Không cần gọi tool, trả lời trực tiếp.",
                    "final_answer": answer
                })
                return {
                    "status": "completed",
                    "answer": answer,
                    "iterations": iteration,
                    "trace": self.trace
                }

            action = actions.pop(0)
            action_name = action["name"].strip().lower()
            tool = TOOL_MAP.get(action_name)
            if tool is None:
                observation = {"error": f"Unknown tool: {action_name}"}
            else:
                try:
                    observation = tool(**action["args"])
                except (TypeError, ValueError, KeyError) as exc:
                    observation = {"error": str(exc)}

            observations.append((action_name, observation))
            self.trace.append({
                "step": iteration,
                "thought": f"Gọi tool {action_name} để lấy dữ liệu.",
                "action": json.loads(json.dumps({
                    "name": action_name,
                    "args": action["args"]
                })),
                "observation": observation
            })

            if not actions:
                answer_parts = []
                for name, result in observations:
                    if name == "get_flight_info":
                        if result:
                            flights = ", ".join(
                                f"{flight['flight_number']} ({flight['price_vnd']:,} VND)"
                                for flight in result
                            )
                            answer_parts.append(f"Chuyến bay phù hợp: {flights}.")
                        else:
                            answer_parts.append("Không tìm thấy chuyến bay phù hợp.")
                    elif name == "get_weather_forecast":
                        if "error" in result:
                            answer_parts.append(f"Lỗi thời tiết: {result['error']}.")
                        else:
                            answer_parts.append(
                                f"Thời tiết {result['city']}: {result['temperature_c']}°C, "
                                f"{result['condition']}. {result['recommendation']}"
                            )
                answer = " ".join(answer_parts)
                if len(observations) == 1:
                    self.trace[-1]["final_answer"] = answer
                else:
                    self.trace.append({
                        "step": iteration + 1,
                        "thought": "Đã đủ dữ liệu từ các tool.",
                        "final_answer": answer
                    })
                    iteration += 1
                return {
                    "status": "completed",
                    "answer": answer,
                    "iterations": iteration,
                    "trace": self.trace
                }

        return {
            "status": "max_iterations_reached",
            "answer": "Không thể hoàn thành trong số bước tối đa.",
            "iterations": iteration,
            "trace": self.trace
        }

def main():
    user_query = "Tìm cho tôi chuyến bay từ HAN đi SGN dưới 2 triệu, rồi cho biết thời tiết SGN nên mặc gì?"
    
    print("=== RUNNING CHATBOT BASELINE ===")
    chatbot = ChatbotBaseline()
    print(chatbot.query(user_query))
    
    print("\n=== RUNNING REACT AGENT ===")
    agent = ReActAgent(max_iterations=5)
    result = agent.run(user_query)
    print("Result:", result)
    print("Trace Log:", json.dumps(agent.trace, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()