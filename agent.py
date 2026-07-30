from dotenv import load_dotenv
load_dotenv()
import json, time, uuid, os, io, contextlib, threading, traceback
from openai import OpenAI

client = OpenAI(api_key=os.environ["AIPIPE_TOKEN"], base_url="https://aipipe.org/openai/v1")
LOG_PATH = "logs/run.jsonl"

def log(entry: dict):
    entry["ts"] = time.time()
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")

def run_python(code: str) -> str:
    out = io.StringIO()
    result = {}
    def target():
        env = {"__name__": "__main__"}
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                exec(code, env)
        except Exception:
            out.write("\n" + traceback.format_exc(limit=4))
    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(60)
    if t.is_alive():
        return "ERROR: code timed out after 60s"
    text = out.getvalue()
    return text[-8000:] if text else "(no output — use print())"

tools = [{
    "type": "function",
    "function": {
        "name": "run_python",
        "description": "Run Python code, get printed output. pandas, numpy, requests, bs4 available. Network available. Always print() what you need to see.",
        "parameters": {
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"]
        }
    }
}]

SYSTEM_PROMPT = """You are an expert data-analyst agent answering questions.
Use run_python to fetch and compute real answers — do not guess numbers you can compute. For well-known published stats, you may answer from knowledge if fetching fails.
The message specifies the exact JSON shape wanted. When ready, reply with ONLY that JSON object — no prose, no markdown fences.
Match the requested shape EXACTLY (keys, nesting, types).
NEVER invent placeholder/sample/hypothetical data (e.g. 'State A', 'Item 1') to compute an answer. 
If a Python library is missing or a real data source can't be fetched, say so in your reasoning and try another approach (different URL, or answer from verified general knowledge) — do not fabricate numbers.
If a fetched URL returns 404, an error, or clearly irrelevant content, do not retry the same broken URL — search for the correct one or try a different approach."""

def extract_json(text: str):
    import re
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.M)
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if esc:
            esc = False; continue
        if c == "\\":
            esc = True; continue
        if c == '"':
            in_str = not in_str; continue
        if in_str:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i+1])
                except json.JSONDecodeError:
                    return None
    return None

def answer_question(question: str) -> str:
    run_id = str(uuid.uuid4())
    log({"run_id": run_id, "type": "input", "question": question})

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question}
    ]

    final_text = None
    for step in range(8):
        try:
            resp = client.chat.completions.create(
                model="gpt-4.1", messages=messages, tools=tools, temperature=0
            )
        except Exception as e:
            log({"run_id": run_id, "type": "error", "error": str(e)})
            break
        msg = resp.choices[0].message

        if msg.tool_calls:
            messages.append(msg)
            for call in msg.tool_calls:
                try:
                    code = json.loads(call.function.arguments).get("code", "")
                except Exception:
                    code = call.function.arguments
                log({"run_id": run_id, "type": "tool_call", "step": step, "code": code[:2000]})
                output = run_python(code)
                log({"run_id": run_id, "type": "tool_result", "step": step, "output": output[:2000]})
                messages.append({"role": "tool", "tool_call_id": call.id, "content": output})
            continue

        final_text = msg.content or ""
        break

    obj = extract_json(final_text) if final_text else None
    if obj is None:
        obj = {"answer": (final_text or "unable to determine").strip()[:1000]}
    if "answer" not in obj:
        obj = {"answer": obj}

    text = json.dumps(obj, ensure_ascii=False)
    log({"run_id": run_id, "type": "output", "response": text})
    return text
