import json, time, uuid, os, requests
from openai import OpenAI

client = OpenAI(api_key=os.environ["AIPIPE_TOKEN"], base_url="https://aipipe.org/openai/v1")
LOG_PATH = "logs/run.jsonl"

def log(entry: dict):
    entry["ts"] = time.time()
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")

def fetch_url(url: str) -> str:
    r = requests.get(url, timeout=15)
    return r.text[:5000]

tools = [{
    "type": "function",
    "function": {
        "name": "fetch_url",
        "description": "Fetch the content of a public URL (e.g. dataset, CSV, webpage)",
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"]
        }
    }
}]

def answer_question(question: str) -> str:
    run_id = str(uuid.uuid4())
    log({"run_id": run_id, "type": "input", "question": question})
    messages = [
        {"role": "system", "content": (
            "You are a data analyst. Use fetch_url to pull real data when the question "
            "references a dataset or link. Then answer. The question specifies the exact "
            "JSON shape required. Reply with ONLY that JSON object, nothing else."
        )},
        {"role": "user", "content": question}
    ]
    for _ in range(3):
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=tools,
            temperature=0
        )
        msg = resp.choices[0].message
        if msg.tool_calls:
            messages.append(msg)
            for call in msg.tool_calls:
                args = json.loads(call.function.arguments)
                result = fetch_url(args["url"])
                log({"run_id": run_id, "type": "tool_call", "url": args["url"]})
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result
                })
            continue
        text = msg.content.strip()
        log({"run_id": run_id, "type": "output", "response": text})
        return text
    return json.dumps({"answer": None, "error": "max_tool_calls_exceeded"})
