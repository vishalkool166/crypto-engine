"""Optional live provider check: python -m scripts.check_groq (never prints keys)."""
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
from research.groq_provider import candidates, complete


async def main():
    if not os.getenv("GROQ_API_KEY"):
        print("No GROQ_API_KEY found. Set it in the existing server .env, not in source control.")
        return 2
    print("Configured candidate models:",", ".join(candidates()))
    try:
        response=await complete([{"role":"user","content":"Reply with only the word READY."}],max_tokens=150)
    except Exception as error:
        print("Model check failed:",type(error).__name__,"(check Groq console permissions and account limits)")
        return 1
    print("Provider response using",response["model"],":",response["answer"][:100])
    return 0

if __name__=="__main__":
    raise SystemExit(asyncio.run(main()))
