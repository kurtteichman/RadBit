def generate_faqs(history: list[dict]) -> list[dict]:
    if not history:
        return []

    inputs = [entry["input"] for entry in history][-20:]

    system_msg = {
        "role": "system",
        "content": (
            "You are an expert assistant that reads user support request descriptions "
            "and groups them by technical theme (e.g., VPN issues, login loops). "
            "For each theme, produce a JSON object with keys:\n"
            "- question: a short user-like question\n"
            "- steps: a list of clear self-help suggestions\n"
            "- input_example: the exact original user request most relevant to this theme\n"
            "Return up to five objects as a JSON array."
        ),
    }
    user_msg = {
        "role": "user",
        "content": f"Here are recent support requests:\n{json.dumps(inputs, indent=2)}"
    }

    try:
        llm = _client.chat.completions.create(
            model="gpt-4o",
            messages=[system_msg, user_msg],
            temperature=0.3,
        )
        content = llm.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content.removeprefix("```json").removesuffix("```").strip()
        parsed = json.loads(content)
        if isinstance(parsed, str):
            parsed = json.loads(parsed)

        results = []
        for faq in parsed:
            input_example = faq.get("input_example", "")
            triage = run_async_task(Runner.run(triage_agent, input_example))
            dept = triage.final_output.department
            contact = SUPPORT_DIRECTORY.get(dept, {})
            steps = faq.get("steps", [])
            answer = "Self-Help Steps:\n" + "\n".join(f"- {s}" for s in steps)
            answer += "\n\nRecommended Support Contact:"
            answer += f"\nDepartment: {dept}"
            if contact.get("phone"):
                answer += f"\nPhone: {contact['phone']}"
            if contact.get("email"):
                answer += f"\nEmail: {contact['email']}"
            results.append({"question": faq.get("question", "FAQ"), "answer": answer})

        return results

    except Exception as e:
        return [{"question": "OpenAI API call failed", "answer": str(e)}]

    return []
